"""Estime la quantite de NaOH necessaire a partir du pH et du TAC.

But du programme
-----------------
Le programme estime le volume de soude liquide (NaOH) a ajouter pour faire
passer le pH d'une piscine d'une valeur initiale vers une valeur cible. Il tient
compte du TAC lorsque celui-ci provient essentiellement des bicarbonates.

Ce qui est calcule
------------------
Le TAC est converti de ppm en equivalents chimiques, puis le programme utilise
l'equilibre CO2 / bicarbonate / carbonate pour estimer la quantite de base qui
modifierait l'alcalinite jusqu'au pH cible. La quantite de NaOH est enfin
convertie en litres avec la concentration de 300 g/L.

Limites importantes
-------------------
Hypotheses : 25 degC, TAC exprime en ppm (mg/L) de CaCO3, systeme carbonate
ferme. Une piscine reelle echange du CO2 avec l'air et peut contenir du chlore,
des acides ou d'autres produits. Le resultat est donc une estimation de
laboratoire, pas une consigne de dosage. Un resultat tres grand signale souvent
des mesures pH/TAC incompatibles ou un apport d'acide non pris en compte.
"""

K1 = 10 ** -6.35
K2 = 10 ** -10.33
KW = 1e-14
MASSE_MOLAIRE_NAOH_G_MOL = 39.997
CONCENTRATION_NAOH_G_L = 300.0


def lire_nombre(message, defaut):
    """Lit un nombre positif ; Entree utilise la valeur par defaut."""
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


def alcalinite_mol_eq_l(tac_ppm_caco3):
    """Convertit un TAC en ppm CaCO3 en equivalents par litre."""
    return tac_ppm_caco3 / 50_043.0


def fractions_carbonate(ph):
    """Retourne les fractions CO2, HCO3- et CO3-- du carbone inorganique."""
    h = 10 ** (-ph)
    denominateur = h * h + K1 * h + K1 * K2
    return h * h / denominateur, K1 * h / denominateur, K1 * K2 / denominateur


def alcalinite(carbone_inorganique_mol_l, ph):
    """Calcule l'alcalinite totale (equivalents/L) du systeme carbonate."""
    _, hco3, co3 = fractions_carbonate(ph)
    h = 10 ** (-ph)
    return carbone_inorganique_mol_l * (hco3 + 2 * co3) + KW / h - h


def carbone_depuis_tac(tac_eq_l, ph):
    """Deduit le carbone inorganique total du TAC et du pH mesures."""
    _, hco3, co3 = fractions_carbonate(ph)
    h = 10 ** (-ph)
    return (tac_eq_l - KW / h + h) / (hco3 + 2 * co3)


def calculer_dosage(volume_m3, ph_initial, ph_cible, tac_ppm):
    """Calcule l'estimation de NaOH pour les mesures fournies."""
    tac_initial = alcalinite_mol_eq_l(tac_ppm)
    carbone = carbone_depuis_tac(tac_initial, ph_initial)
    tac_cible = alcalinite(carbone, ph_cible)
    moles_naoh = (tac_cible - tac_initial) * volume_m3 * 1_000
    concentration_mol_l = CONCENTRATION_NAOH_G_L / MASSE_MOLAIRE_NAOH_G_MOL
    return carbone, tac_cible, moles_naoh, moles_naoh / concentration_mol_l


def main():
    print("=" * 72)
    print("DOSAGE ESTIME DE NaOH 300 g/L - PISCINE AVEC TAMPON BICARBONATE")
    print("=" * 72)
    print("\nBut : estimer le volume de soude necessaire pour augmenter le pH.")
    print("Le TAC mesure la resistance de l'eau a une variation de pH :")
    print("plus il est eleve, plus il faut de produit pour modifier le pH.")
    print("Ici, le TAC est suppose principalement constitue de bicarbonates.\n")
    print("Le produit est fixe a 300 g de NaOH par litre, soit 7.501 mol/L.")
    print("Entree seule = valeur entre crochets.\n")
    volume_m3 = lire_nombre("Volume de la piscine en m3", 46)
    ph_initial = lire_nombre("pH initial", 4.1)
    ph_cible = lire_nombre("pH cible", 7.2)
    tac_ppm = lire_nombre("TAC en ppm (mg/L en equivalent CaCO3)", 50)
    if ph_cible <= ph_initial:
        print("Le pH cible doit etre superieur au pH initial pour ajouter du NaOH.")
        return
    carbone, tac_cible, moles_naoh, litres_naoh = calculer_dosage(volume_m3, ph_initial, ph_cible, tac_ppm)
    print(f"\nConcentration de NaOH : {CONCENTRATION_NAOH_G_L / MASSE_MOLAIRE_NAOH_G_MOL:.3f} mol/L")
    print(f"Carbone inorganique deduit : {carbone:.4f} mol/L")
    print(f"TAC calcule a pH {ph_cible:.2f} : {tac_cible * 50_043:.0f} ppm CaCO3")
    print(f"Besoin theorique : {moles_naoh:.0f} mol, soit {litres_naoh:.1f} L de NaOH a 300 g/L")
    print("\nLecture des resultats :")
    print("- Le carbone inorganique represente CO2, bicarbonates et carbonates.")
    print("- Le TAC cible est le pouvoir tampon que le modele associe au pH cible.")
    print("- Le besoin theorique est le volume obtenu uniquement avec ces hypotheses.")
    if carbone > 0.01 or litres_naoh > 5:
        print("\nATTENTION : ce resultat est probablement non exploitable en dosage direct.")
        print("Les valeurs pH/TAC impliquent une quantite de carbone anormalement elevee.")
        print("Ne versez pas ce volume. Recalibrez le pH-metre et refaites TAC/pH.")
        print("Faites ensuite un essai sur 1 L d'eau et extrapolez avec de tres petites doses.")
    else:
        print("\nLe resultat reste une estimation : ajoutez uniquement par petites doses,")
        print("filtration en marche, puis re-mesurez avant toute dose supplementaire.")


if __name__ == "__main__":
    main()
