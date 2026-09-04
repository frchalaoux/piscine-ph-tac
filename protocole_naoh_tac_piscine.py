"""Prepare un protocole d'ajustement pH/TAC pour une piscine.

Le protocole separe volontairement les operations :
1. la soude remonte d'abord le pH jusqu'a 6,0 ;
2. le bicarbonate de sodium remonte ensuite le TAC ;
3. une nouvelle mesure permet de finir l'ajustement vers pH 7,2.

Pourquoi separer ? A pH 4,1, le pH et le TAC ne suffisent pas a predire une
dose fiable de NaOH : de l'acide, du CO2 dissous et d'autres produits peuvent
etre presents. En revanche, la quantite de bicarbonate necessaire pour une
hausse de TAC donnee se calcule directement. Les doses de soude sont donc
determinees par un essai sur echantillon, puis extrapolees au bassin.
"""

MASSE_MOLAIRE_NAOH_G_MOL = 39.997
CONCENTRATION_NAOH_G_L = 300.0
MASSE_MOLAIRE_NAHCO3_G_MOL = 84.0066
MASSE_EQUIVALENTE_CACO3_G_EQ = 50.043
TAC_CIBLE_PPM = 80.0
APPORT_BICARBONATE_MAX_KG = 0.5


def lire_nombre(message, defaut):
    """Lit un nombre strictement positif ; Entree choisit la valeur par defaut."""
    while True:
        texte = input(f"{message} [{defaut}] : ").strip().replace(",", ".")
        if not texte:
            return float(defaut)
        try:
            valeur = float(texte)
            if valeur > 0:
                return valeur
        except ValueError:
            pass
        print("Saisissez un nombre strictement positif.")


def lire_nombre_optionnel(message):
    """Lit un nombre positif ou renvoie None si aucune valeur n'est donnee."""
    while True:
        texte = input(message).strip().replace(",", ".")
        if not texte:
            return None
        try:
            valeur = float(texte)
            if valeur > 0:
                return valeur
        except ValueError:
            pass
        print("Saisissez un nombre strictement positif, ou Entree pour ignorer.")


def masse_bicarbonate_kg(volume_m3, tac_actuel_ppm, tac_vise_ppm):
    """Calcule la masse de NaHCO3 pour augmenter le TAC (ppm en CaCO3)."""
    hausse_ppm = max(0.0, tac_vise_ppm - tac_actuel_ppm)
    volume_l = volume_m3 * 1_000
    # ppm CaCO3 = mg/L ; conversion de l'equivalent CaCO3 vers NaHCO3.
    masse_g = hausse_ppm * volume_l / 1_000 * (
        MASSE_MOLAIRE_NAHCO3_G_MOL / MASSE_EQUIVALENTE_CACO3_G_EQ
    )
    return masse_g / 1_000


def volume_naoh_minimum_litres(volume_m3, ph_depart, ph_arrivee):
    """Donne uniquement la limite theorique liee aux ions libres, sans tampon."""
    h_depart = 10 ** (-ph_depart)
    oh_depart = 10 ** (ph_depart - 14)
    h_arrivee = 10 ** (-ph_arrivee)
    oh_arrivee = 10 ** (ph_arrivee - 14)
    moles = volume_m3 * 1_000 * (h_depart - oh_depart + oh_arrivee - h_arrivee)
    return moles / (CONCENTRATION_NAOH_G_L / MASSE_MOLAIRE_NAOH_G_MOL)


def extrapoler_naoh_litres(volume_piscine_m3, volume_echantillon_ml, dose_naoh_ml):
    """Extrapole au bassin une dose de NaOH determinee sur un echantillon."""
    return dose_naoh_ml * volume_piscine_m3 * 1_000 / volume_echantillon_ml


def fractionner_dose_ml(volume_total_ml):
    """Decoupe une dose en ajouts de plus en plus petits.

    Le fractionnement ne change pas la quantite issue de l'essai sur
    echantillon. Il rend l'approche du pH cible plus prudente.
    """
    restant = round(volume_total_ml, 1)
    etapes = []
    for dose_ml in (250, 100, 50):
        nombre = 0
        # On garde toujours la derniere fraction pour un dosage plus fin.
        while restant > dose_ml:
            nombre += 1
            restant = round(restant - dose_ml, 1)
        if nombre:
            etapes.append((nombre, dose_ml))
    if restant > 0:
        etapes.append((1, restant))
    return etapes


def fractionner_bicarbonate_kg(masse_totale_kg):
    """Decoupe le bicarbonate en apports de 0,5 kg maximum."""
    restant = round(masse_totale_kg, 3)
    apports = []
    while restant > APPORT_BICARBONATE_MAX_KG:
        apports.append(APPORT_BICARBONATE_MAX_KG)
        restant = round(restant - APPORT_BICARBONATE_MAX_KG, 3)
    if restant > 0:
        apports.append(restant)
    return apports


def afficher_fractionnement(volume_litres):
    """Affiche un plan d'ajouts successifs pour une dose deja evaluee."""
    volume_ml = volume_litres * 1_000
    print("Plan de fractionnement de cette estimation :")
    for nombre, dose_ml in fractionner_dose_ml(volume_ml):
        unite = f"{dose_ml:.0f}" if dose_ml >= 1 else f"{dose_ml:.1f}"
        pluriel = "s" if nombre > 1 else ""
        print(f"- {nombre} ajout{pluriel} de {unite} mL, avec mesure pH apres chaque ajout.")
    print("Arretez des que le pH cible de l'etape est atteint, meme s'il reste des doses.")


def afficher_essai_echantillon(volume_m3, etape):
    """Propose l'extrapolation d'un essai de soude sur un echantillon."""
    print(f"\nEssai facultatif - {etape}")
    print("Sur un echantillon, ajoutez la soude avec une pipette, melangez et mesurez.")
    volume_echantillon = lire_nombre_optionnel("Volume de l'echantillon en mL (Entree pour ignorer) : ")
    if volume_echantillon is None:
        return
    dose = lire_nombre("Dose de NaOH trouvee sur cet echantillon, en mL", 0.1)
    total = extrapoler_naoh_litres(volume_m3, volume_echantillon, dose)
    print(f"Extrapolation : {total:.2f} L de NaOH 300 g/L pour {volume_m3:.1f} m3.")
    print("N'ajoutez pas tout d'un coup : fractionnez, laissez circuler et re-mesurez.")
    afficher_fractionnement(total)


def main():
    print("=" * 72)
    print("PROTOCOLE pH + TAC : NaOH PUIS BICARBONATE DE SODIUM")
    print("=" * 72)
    print("Ce programme fournit un protocole, pas une dose unique a verser.")
    print("Les valeurs entre crochets correspondent a votre bassin.\n")

    volume_m3 = lire_nombre("Volume de la piscine en m3", 46)
    ph_depart = lire_nombre("pH de depart", 4.1)
    ph_palier = lire_nombre("Palier avant bicarbonate", 6.0)
    ph_final = lire_nombre("pH final vise", 7.2)
    tac_initial = lire_nombre("TAC mesure en ppm CaCO3", 50)

    if not ph_depart < ph_palier < ph_final:
        print("Les pH doivent respecter : pH de depart < palier < pH final.")
        return

    print("\nETAPE 1 - Remonter le pH jusqu'au palier")
    limite = volume_naoh_minimum_litres(volume_m3, ph_depart, ph_palier)
    print(f"La limite theorique sans effet tampon est {limite * 1_000:.0f} mL de NaOH.")
    print("Ce n'est PAS une dose de bassin : a pH 4,1, la demande reelle est inconnue.")
    print("Faites un essai sur echantillon, puis corrigez par petites doses avec filtration.")
    afficher_essai_echantillon(volume_m3, f"pH {ph_depart:.1f} vers pH {ph_palier:.1f}")

    print("\nETAPE 2 - A pH proche de 6,0, mesurer de nouveau le TAC")
    print("Le bicarbonate est ajoute a cette etape, pas au debut, afin de retablir")
    print("le pouvoir tampon avant le dernier ajustement de pH.")
    tac_a_6 = lire_nombre("TAC re-mesure au palier (utilisez 50 si non mesure)", tac_initial)
    bicarbonate_kg = masse_bicarbonate_kg(volume_m3, tac_a_6, TAC_CIBLE_PPM)
    if bicarbonate_kg == 0:
        print(f"Le TAC est deja au moins egal a {TAC_CIBLE_PPM:.0f} ppm : pas de bicarbonate calcule.")
    else:
        print(f"Objectif TAC : {TAC_CIBLE_PPM:.0f} ppm CaCO3.")
        print(f"Ajouter environ {bicarbonate_kg:.2f} kg de bicarbonate de sodium (NaHCO3).")
        print("Pour 46 m3, passer de 50 a 80 ppm correspond a environ 2,32 kg.")
        print("Ajouts de bicarbonate, en poudre devant les buses avec filtration en marche :")
        for numero, apport_kg in enumerate(fractionner_bicarbonate_kg(bicarbonate_kg), start=1):
            print(f"- apport {numero} : {apport_kg:.2f} kg")
        print("Laissez le produit se dissoudre et circuler entre les apports.")
        print("Le bicarbonate peut aussi modifier le pH : re-mesurez pH et TAC apres")
        print("la derniere dissolution avant de passer a l'etape 3.")
        print("Le recipient de 10 L n'est pas requis pour le bicarbonate ajoute en poudre.")

    print("\nETAPE 3 - Finaliser vers le pH cible")
    print("Apres stabilisation, mesurez a nouveau pH et TAC. Utilisez un nouvel essai")
    print("sur echantillon pour determiner la petite dose de NaOH restante vers pH 7,2.")
    afficher_essai_echantillon(volume_m3, f"le palier vers pH {ph_final:.1f}")

    print("\nSECURITE : la soude a 300 g/L est corrosive. Portez les protections prevues")
    print("par la FDS, ne melangez jamais les produits et respectez l'etiquette du fabricant.")


if __name__ == "__main__":
    main()
