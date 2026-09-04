"""Calcul des volumes d'acide ou de soude pour ajuster le pH d'une piscine."""

VOLUME_PISCINE_L = 22_000.0
CONCENTRATION_HCL = 6.3e-2
CONCENTRATION_NAOH = 5.3e-2
PH_CIBLE = 7.4


def concentration_h3o(ph):
    """Retourne la concentration en ions H3O+ (mol/L) pour un pH donné."""
    return 10 ** (-ph)


def concentration_oh(ph):
    """Retourne la concentration en ions OH- (mol/L) pour un pH donné."""
    return 10 ** (ph - 14)


def calcul_pH(ph_initial, ph_final):
    """Calcule le volume de solution d'HCl à ajouter, en litres.

    Cette fonction est adaptée à une baisse de pH : le résultat est positif
    lorsque ``ph_initial`` est supérieur à ``ph_final``.
    """
    variation = (
        concentration_h3o(ph_final)
        - concentration_h3o(ph_initial)
        + concentration_oh(ph_initial)
        - concentration_oh(ph_final)
    )
    return VOLUME_PISCINE_L * variation / CONCENTRATION_HCL


def calcul_pH_2(ph_initial, ph_final):
    """Calcule le volume de solution de NaOH à ajouter, en litres.

    Cette fonction est adaptée à une hausse de pH : le résultat est positif
    lorsque ``ph_initial`` est inférieur à ``ph_final``.
    """
    variation = (
        concentration_oh(ph_final)
        - concentration_oh(ph_initial)
        + concentration_h3o(ph_initial)
        - concentration_h3o(ph_final)
    )
    return VOLUME_PISCINE_L * variation / CONCENTRATION_NAOH


def afficher_tableau_hcl(ph_final):
    print(f"En utilisant une solution de HCl = {CONCENTRATION_HCL:.1e} M :")
    print(f"pour passer a pH = {ph_final:.1f} a partir d'un pH > {ph_final:.1f}:")
    print()

    for dixieme in range(1, 12):
        ph_initial = ph_final + dixieme / 10
        volume = calcul_pH(ph_initial, ph_final)
        print(f"pH = {ph_initial:.2f} -> {volume:.2f} L")


def afficher_tableau_naoh(ph_final):
    print(f"En utilisant une solution de soude (NaOH) = {CONCENTRATION_NAOH:.1e} M :")
    print(f"pour passer a pH = {ph_final:.1f} a partir d'un pH < {ph_final:.1f}:")
    print()

    for dixieme in range(14, 0, -1):
        ph_initial = ph_final - dixieme / 10
        volume = calcul_pH_2(ph_initial, ph_final)
        print(f"pH = {ph_initial:.2f} -> {volume:.2f} L")


def main():
    afficher_tableau_hcl(PH_CIBLE)
    print()
    afficher_tableau_naoh(PH_CIBLE)


if __name__ == "__main__":
    main()
