from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt


# ============================================================
# 1. Einstellungen
# ============================================================

DATEI = Path(r"C:\Users\chris\Documents\BANKUMSAETZE\Aktien\aktienkurse.csv")

SPALTEN = [
    "Symbol",
    "Kürzel",
    "Name",
    "Datum",
    "Kurs",
    "Währung",
    "Handelsplatz",
    "Abfragedatum"
]


# ============================================================
# 2. CSV-Datei vorbereiten
# ============================================================

def datei_laden():

    # Ordner bei Bedarf anlegen
    DATEI.parent.mkdir(parents=True, exist_ok=True)

    if DATEI.exists():
        df = pd.read_csv(DATEI, dtype={"Symbol": str})
        print("Vorhandene Kursdatei wurde geladen.")

        # Falls eine ältere Version der Datei verwendet wird
        for spalte in SPALTEN:
            if spalte not in df.columns:
                df[spalte] = pd.NA

        df = df[SPALTEN]

    else:
        df = pd.DataFrame(columns=SPALTEN)
        df.to_csv(DATEI, index=False, encoding="utf-8-sig")
        print("Neue Kursdatei wurde angelegt.")

    return df


def datei_speichern(df):
    df.to_csv(DATEI, index=False, encoding="utf-8-sig")


# ============================================================
# 3. Aktieninformationen und Kurse abfragen
# ============================================================

def aktie_suchen(eingabe):

    # Zuerst versuchen wir, den Begriff über Yahoo Finance
    # als Aktienname oder Börsenkürzel zu finden.
    try:
        ergebnis = yf.Search(eingabe, max_results=8)
        treffer = ergebnis.quotes

        treffer = [
            t for t in treffer
            if t.get("quoteType") == "EQUITY"
            and t.get("symbol")
        ]

    except Exception:
        treffer = []

    if not treffer:
        # Fallback: Eingabe direkt als Yahoo-Symbol verwenden
        symbol = eingabe.upper()

        try:
            info = yf.Ticker(symbol).get_info()

            if not info.get("longName") and not info.get("shortName"):
                print("Keine passende Aktie gefunden.")
                return None

            return {
                "symbol": symbol,
                "name": info.get("longName")
                        or info.get("shortName")
                        or symbol
            }

        except Exception:
            print("Aktie konnte nicht gefunden werden.")
            return None

    print("\nGefundene Aktien:")

    for i, treffer_eintrag in enumerate(treffer, start=1):
        name = (
            treffer_eintrag.get("longname")
            or treffer_eintrag.get("shortname")
            or treffer_eintrag["symbol"]
        )

        boerse = treffer_eintrag.get("exchange", "unbekannt")

        print(
            f"{i}: {treffer_eintrag['symbol']} | "
            f"{name} | Börse: {boerse}"
        )

    print("X: Abbrechen")

    auswahl = input("Bitte Aktie auswählen: ").strip()

    if auswahl.upper() == "X":
        return None

    try:
        index = int(auswahl) - 1

        if index < 0 or index >= len(treffer):
            raise ValueError

        t = treffer[index]

        return {
            "symbol": t["symbol"],
            "name": (
                t.get("longname")
                or t.get("shortname")
                or t["symbol"]
            )
        }

    except ValueError:
        print("Ungültige Auswahl.")
        return None


def kurs_abfragen(symbol):

    aktie = yf.Ticker(symbol)

    # Die letzten fünf Kalendertage abfragen.
    # So finden wir auch nach einem Wochenende
    # den letzten verfügbaren Handelstag.
    historie = aktie.history(
        period="5d",
        interval="1d",
        auto_adjust=False
    )

    if historie.empty:
        print(f"Keine Kursdaten für {symbol} erhalten.")
        return None

    # Letzte Zeile = letzter verfügbarer Handelstag
    letzte_zeile = historie.dropna(subset=["Close"]).iloc[-1]

    kurs_datum = historie.dropna(subset=["Close"]).index[-1]
    kurs_datum = pd.Timestamp(kurs_datum).date().isoformat()

    # Börseninformationen abrufen
    try:
        info = aktie.get_info()
    except Exception:
        info = {}

    name = (
        info.get("longName")
        or info.get("shortName")
        or symbol
    )

    # Yahoo verwendet je nach Börse eigene Kürzel.
    # Das sind Beispiele, keine vollständige Zuordnung.
    handelsplatz = info.get("exchange", "unbekannt")

    if symbol.endswith(".DE"):
        handelsplatz = "ETR"

    return {
        "Symbol": symbol,
        "Kürzel": symbol.split(".")[0],
        "Name": name,
        "Datum": kurs_datum,
        "Kurs": float(letzte_zeile["Close"]),
        "Währung": info.get("currency", "unbekannt"),
        "Handelsplatz": handelsplatz,
        "Abfragedatum": date.today().isoformat()
    }


def kurs_speichern(df, symbol):

    datensatz = kurs_abfragen(symbol)

    if datensatz is None:
        return df

    # Pro Aktie und Abfragetag nur einen Datensatz speichern.
    # Bei einem erneuten Versuch am selben Tag wird
    # der bestehende Tagesdatensatz ersetzt.
    bedingung = (
        (df["Symbol"] == symbol)
        & (df["Abfragedatum"] == datensatz["Abfragedatum"])
    )

    df = df.loc[~bedingung].copy()

    df = pd.concat(
        [df, pd.DataFrame([datensatz])],
        ignore_index=True
    )

    datei_speichern(df)

    print(
        f"Kurs gespeichert: {datensatz['Name']} – "
        f"{datensatz['Kurs']:.2f} {datensatz['Währung']} "
        f"({datensatz['Datum']})"
    )

    return df


# ============================================================
# 4. Automatische Aktualisierung beim Programmstart
# ============================================================

def kurse_aktualisieren(df):

    if df.empty:
        print("Noch keine Aktien hinterlegt.")
        return df

    heute = date.today().isoformat()

    # Alle bisher bekannten Symbole
    symbole = df["Symbol"].dropna().unique()

    for symbol in symbole:

        # Prüfen, ob für diese Aktie heute schon abgefragt wurde
        bereits_abgefragt = (
            (df["Symbol"] == symbol)
            & (df["Abfragedatum"] == heute)
        ).any()

        if bereits_abgefragt:
            print(f"{symbol}: heute bereits aktualisiert.")
            continue

        print(f"Aktualisiere {symbol} ...")
        df = kurs_speichern(df, symbol)

    return df


# ============================================================
# 5. Alle Aktien mit dem jeweils letzten Kurs anzeigen
# ============================================================

def aktien_anzeigen(df, symbol=None):

    if df.empty:
        print("Es sind noch keine Kurse gespeichert.")
        return

    daten = df.copy()

    if symbol is not None:
        daten = daten[daten["Symbol"] == symbol]

    if daten.empty:
        print("Keine passenden Daten gefunden.")
        return

    # Je Aktie nur den zuletzt gespeicherten Datensatz anzeigen
    daten = (
        daten.sort_values("Abfragedatum")
        .drop_duplicates(subset="Symbol", keep="last")
        .sort_values("Kürzel")
    )

    ausgabe = daten[
        [
            "Kürzel",
            "Name",
            "Datum",
            "Kurs",
            "Währung",
            "Handelsplatz"
        ]
    ].copy()

    ausgabe["Kurs"] = ausgabe["Kurs"].map(
        lambda x: f"{x:.2f}" if pd.notna(x) else ""
    )

    print()
    print(ausgabe.to_string(index=False))
    print()


# ============================================================
# Historische Kurse für alle gespeicherten Aktien vervollständigen
# ============================================================

def alle_historischen_kurse_auffuellen(df):

    if df.empty:
        print("Es sind noch keine Aktien gespeichert.")
        return df

    # Alle unterschiedlichen Aktiensymbole ermitteln
    symbole = df["Symbol"].dropna().unique()

    print("\nHistorische Kurse ab dem 01.01.2026 prüfen")
    print(f"Anzahl der Aktien: {len(symbole)}\n")

    for symbol in symbole:

        print("-" * 50)
        print(f"Prüfe historische Kurse für {symbol} ...")

        # Vorhandene Funktion wiederverwenden.
        # Bereits gespeicherte Handelstage werden übersprungen.
        df = historische_kurse_importieren(df, symbol)

    # Zum Abschluss nochmals die gesamte Datei speichern
    datei_speichern(df)

    print("\nDie Prüfung aller Aktien ist abgeschlossen.")

    return df


# ============================================================
# Historische Kurse seit dem 01.01.2026 importieren
# ============================================================

def historische_kurse_importieren(df, symbol):

    aktie = yf.Ticker(symbol)

    try:
        # end ist exklusiv: Der heutige Tag wird hier
        # bewusst nicht mit importiert.
        historie = aktie.history(
            start="2026-01-01",
            end=date.today().isoformat(),
            interval="1d",
            auto_adjust=False
        )

        info = aktie.get_info()

    except Exception as e:
        print(f"Fehler beim Abrufen der Historie: {e}")
        return df

    if historie.empty:
        print("Keine historischen Kurse gefunden.")
        return df

    name = (
        info.get("longName")
        or info.get("shortName")
        or symbol
    )

    waehrung = info.get("currency", "unbekannt")
    handelsplatz = info.get("exchange", "unbekannt")

    if symbol.endswith(".DE"):
        handelsplatz = "ETR"

    anzahl = 0

    # Jeden verfügbaren Handelstag durchgehen
    for kurs_datum, zeile in historie.iterrows():

        if pd.isna(zeile["Close"]):
            continue

        datum = pd.Timestamp(kurs_datum).date().isoformat()

        # Prüfen, ob dieser Kurs für den Handelstag
        # bereits in der CSV-Datei vorhanden ist
        bereits_vorhanden = (
            (df["Symbol"] == symbol)
            & (df["Datum"].astype(str) == datum)
        ).any()

        if bereits_vorhanden:
            continue

        neuer_kurs = {
            "Symbol": symbol,
            "Kürzel": symbol.split(".")[0],
            "Name": name,
            "Datum": datum,
            "Kurs": float(zeile["Close"]),
            "Währung": waehrung,
            "Handelsplatz": handelsplatz,

            # Bei importierten historischen Kursen verwenden
            # wir das Kursdatum, damit die bestehende
            # Tagesaktualisierung nicht fälschlich übersprungen wird.
            "Abfragedatum": datum
        }

        df = pd.concat(
            [df, pd.DataFrame([neuer_kurs])],
            ignore_index=True
        )

        anzahl += 1

    datei_speichern(df)

    print(f"{anzahl} historische Kurse für {symbol} gespeichert.")

    return df



# ============================================================
# 6. Neue Aktie hinzufügen
# ============================================================

def aktie_hinzufuegen(df):

    eingabe = input(
        "Aktienname oder Yahoo-Symbol eingeben (X = zurück): "
    ).strip()

    if eingabe.upper() == "X":
        return df

    if not eingabe:
        print("Bitte eine Eingabe machen.")
        return df

    auswahl = aktie_suchen(eingabe)

    if auswahl is None:
        return df

    symbol = auswahl["symbol"]

    # Prüfen, ob die Aktie bereits hinterlegt ist
    vorhanden = df[df["Symbol"] == symbol]

    if not vorhanden.empty:
        print("\nDiese Aktie ist bereits gespeichert.")
        aktien_anzeigen(df, symbol)
        return df

    # NEU: Zuerst die historischen Kurse importieren
    print(f"\nImportiere historische Kurse für {symbol} ...")

    df = historische_kurse_importieren(df, symbol)

    # Anschließend den aktuell verfügbaren Kurs abfragen
    print(f"\nFrage zusätzlich den aktuellen Kurs für {symbol} ab ...")

    df = kurs_speichern(df, symbol)

    return df

# ============================================================
# 7. Historische Kurse tabellarisch anzeigen
# ============================================================

def historische_kurse(df):

    # Zuerst alle Aktien mit dem letzten Kurs anzeigen
    print("\nVerfügbare Aktien:")

    aktien_anzeigen(df)

    # Gewünschte Aktie auswählen
    eingabe = input(
        "Aktienname oder Kürzel eingeben (X = zurück): "
    ).strip()

    if eingabe.upper() == "X":
        return

    if eingabe == "":
        print("Bitte ein Kürzel oder einen Namen eingeben.")
        return

    # Passende Aktien anhand des Kürzels oder Namens suchen
    treffer = df[
        df["Symbol"].str.contains(
            eingabe, case=False, na=False, regex=False
        )
        | df["Kürzel"].str.contains(
            eingabe, case=False, na=False, regex=False
        )
        | df["Name"].str.contains(
            eingabe, case=False, na=False, regex=False
        )
    ]

    if treffer.empty:
        print("Keine passende Aktie gefunden.")
        return

    # Falls mehrere Aktien passen, Auswahl ermöglichen
    symbole = treffer["Symbol"].drop_duplicates().tolist()

    if len(symbole) > 1:
        print("\nMehrere Aktien passen zu deiner Eingabe:")

        for i, symbol in enumerate(symbole, start=1):
            name = treffer.loc[
                treffer["Symbol"] == symbol, "Name"
            ].iloc[0]

            print(f"{i}: {name} ({symbol})")

        auswahl = input(
            "Bitte Nummer auswählen (X = zurück): "
        ).strip()

        if auswahl.upper() == "X":
            return

        try:
            symbol = symbole[int(auswahl) - 1]
        except (ValueError, IndexError):
            print("Ungültige Auswahl.")
            return

    else:
        symbol = symbole[0]

    # Alle gespeicherten Kurse dieser Aktie auswählen
    daten = df[df["Symbol"] == symbol].copy()

    # Datumsfelder in Datumswerte umwandeln
    daten["Datum"] = pd.to_datetime(
        daten["Datum"], errors="coerce"
    )

    daten["Abfragedatum"] = pd.to_datetime(
        daten["Abfragedatum"], errors="coerce"
    )

    # Ungültige Kurs- oder Datumswerte entfernen
    daten = daten.dropna(subset=["Datum", "Kurs"])

    # Falls derselbe Handelstag mehrfach vorkommt,
    # den zuletzt abgefragten Kurs für diesen Tag behalten
    daten = (
        daten.sort_values("Abfragedatum")
        .drop_duplicates(subset="Datum", keep="last")
        .sort_values("Datum")
    )

    # Die letzten 20 Kurstage auswählen
    daten = daten.tail(20)

    if daten.empty:
        print("Für diese Aktie sind keine Kurse vorhanden.")
        return

    # Tabelle für die Ausgabe vorbereiten
    ausgabe = daten[
        [
            "Kürzel",
            "Name",
            "Datum",
            "Kurs",
            "Währung",
            "Handelsplatz"
        ]
    ].copy()

    ausgabe["Datum"] = ausgabe["Datum"].dt.strftime("%Y-%m-%d")

    ausgabe["Kurs"] = ausgabe["Kurs"].map(
        lambda x: f"{x:.2f}" if pd.notna(x) else ""
    )

    print(f"\nHistorische Kurse für {daten['Name'].iloc[-1]}")
    print("(Ältester Kurs oben, neuester Kurs unten)\n")
    print(ausgabe.to_string(index=False))
    print()


# ============================================================
# XX. Quartalsübersicht in der Konsole ausgeben
# ============================================================

def quartalsuebersicht_konsole(df):
    """Gibt eine quartalsweise Aktienübersicht in der Konsole aus."""

    # Benötigte Spalten prüfen
    benoetigt = [
        "Symbol", "Kürzel", "Name", "Datum", "Kurs", "Währung"
    ]

    for spalte in benoetigt:
        if spalte not in df.columns:
            print(f"Die Spalte '{spalte}' fehlt in der CSV-Datei.")
            return

    if df.empty:
        print("Es sind noch keine Aktienkurse gespeichert.")
        return

    # Daten vorbereiten
    daten = df.copy()
    daten["Datum"] = pd.to_datetime(daten["Datum"], errors="coerce")
    daten["Kurs"] = pd.to_numeric(daten["Kurs"], errors="coerce")

    # Nur Kurse ab dem 01.01.2026 verwenden
    daten = daten[
        (daten["Datum"] >= "2026-01-01")
        & daten["Kurs"].notna()
    ].copy()

    if daten.empty:
        print("Ab dem 01.01.2026 wurden keine Kurse gefunden.")
        return

    # Doppelte Kurse am selben Tag vermeiden
    sortierspalten = ["Symbol", "Datum"]
    if "Abfragedatum" in daten.columns:
        sortierspalten.append("Abfragedatum")

    daten = daten.sort_values(sortierspalten)
    daten = daten.drop_duplicates(
        subset=["Symbol", "Datum"], keep="last"
    )

    # Quartal jedes Kurses bestimmen
    daten["Quartal"] = daten["Datum"].dt.to_period("Q")

    # Je Aktie und Quartal den ersten verfügbaren Kurs nehmen
    quartalskurse = (
        daten.sort_values("Datum")
        .drop_duplicates(subset=["Symbol", "Quartal"], keep="first")
    )

    # Kurswerte für schnellen Zugriff speichern
    kurse = {}
    for _, zeile in quartalskurse.iterrows():
        schluessel = (zeile["Symbol"], zeile["Quartal"])
        kurse[schluessel] = zeile["Kurs"]

    # Stammdaten je Aktie zusammenstellen
    aktien = (
        daten.sort_values("Datum")
        .drop_duplicates(subset=["Symbol"], keep="last")
        [["Symbol", "Kürzel", "Name", "Währung"]]
        .sort_values("Kürzel")
    )

    # Fester Referenzwert: erster verfügbarer Kurs in Q1 2026
    referenz_quartal = pd.Period("2026Q1", freq="Q")

    # Jahre bestimmen, für die Kurse vorhanden sind
    vorhandene_quartale = quartalskurse["Quartal"].unique()
    jahre = sorted(set(q.year for q in vorhandene_quartale))

    # Farben für die Konsole
    ROT = "\033[31m"
    BLAU = "\033[34m"
    RESET = "\033[0m"

    def kurs_formatieren(wert):
        if pd.isna(wert):
            return "-"
        # Deutsche Zahlendarstellung, z. B. 1.234,56
        return f"{wert:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def prozent_formatieren(wert):
        if wert is None or pd.isna(wert):
            return "-"

        text = f"{wert:.0f} %"

        if wert < 50:
            return f"{ROT}{text}{RESET}"
        elif wert > 150:
            return f"{BLAU}{text}{RESET}"
        return text

    # Für jedes Kalenderjahr einen Tabellenblock ausgeben
    for jahr in jahre:
        print()
        print("=" * 100)
        print(f"QUARTALSÜBERSICHT – GESCHÄFTSJAHR {jahr}")
        print("=" * 100)

        # Im Jahr 2026 ist Q1 der Referenzwert.
        # In späteren Jahren werden alle vier Quartale gezeigt.
        quartale_im_jahr = [
            pd.Period(f"{jahr}Q{q}", freq="Q")
            for q in range(1, 5)
            if not (jahr == 2026 and q == 1)
        ]

        # Spaltenüberschriften
        kopf = (
            f"{'Kürzel':<12}"
            f"{'Name':<28}"
            f"{'Währ.':<7}"
            f"{'Q1 2026':>13}"
        )

        for quartal in quartale_im_jahr:
            kurz = f"Q{quartal.quarter} {quartal.year}"
            kopf += f"{kurz + ' Kurs':>13}"
            kopf += f"{'vs. Ref.':>12}"
            kopf += f"{'vs. Vor-Q':>12}"

        print(kopf)
        print("-" * len(kopf))

        # Jede Aktie ausgeben
        for _, aktie in aktien.iterrows():
            symbol = aktie["Symbol"]
            kuerzel = str(aktie["Kürzel"])[:11]
            name = str(aktie["Name"])[:27]
            waehrung = str(aktie["Währung"])[:6]

            referenz = kurse.get((symbol, referenz_quartal))

            zeile_text = (
                f"{kuerzel:<12}"
                f"{name:<28}"
                f"{waehrung:<7}"
                f"{kurs_formatieren(referenz):>13}"
            )

            for quartal in quartale_im_jahr:
                aktueller_kurs = kurse.get((symbol, quartal))
                vorheriger_kurs = kurse.get(
                    (symbol, quartal - 1)
                )

                # Verhältnis zum festen Referenzkurs
                if referenz and aktueller_kurs is not None:
                    ref_prozent = aktueller_kurs / referenz * 100
                else:
                    ref_prozent = None

                # Verhältnis zum unmittelbar vorherigen Quartal
                if vorheriger_kurs and aktueller_kurs is not None:
                    vorquartal_prozent = (
                        aktueller_kurs / vorheriger_kurs * 100
                    )
                else:
                    vorquartal_prozent = None

                zeile_text += f"{kurs_formatieren(aktueller_kurs):>13}"
                zeile_text += f"{prozent_formatieren(ref_prozent):>21}"
                zeile_text += f"{prozent_formatieren(vorquartal_prozent):>21}"

            print(zeile_text)

    print()
    print("Hinweis: Prozentwerte zeigen das Kursverhältnis.")
    print("100 % = gleich hoch, 150 % = 1,5-facher Kurs.")
    print("Rot: unter 50 % | Blau: über 150 %")



# ============================================================
# 8. Kursdiagramm erstellen
# ============================================================

def kursdiagramm(df):

    # NEU: Zuerst alle Aktien mit dem letzten Kurs anzeigen
    print("\nVerfügbare Aktien für das Kursdiagramm:")
    aktien_anzeigen(df)

    # Danach wie bisher die gewünschte Aktie abfragen
    eingabe = input(
        "Aktienname oder Kürzel eingeben (X = zurück): "
    ).strip()

    if eingabe.upper() == "X":
        return

    # Ab hier bleibt dein bisheriger Code unverändert!

    if eingabe.upper() == "X":
        return

    # Eingabe einem gespeicherten Symbol zuordnen
    treffer = df[
        df["Symbol"].str.contains(
            eingabe, case=False, na=False, regex=False
        )
        | df["Name"].str.contains(
            eingabe, case=False, na=False, regex=False
        )
    ]

    if treffer.empty:
        print("Diese Aktie ist nicht in der Datei gespeichert.")
        return

    symbole = treffer["Symbol"].drop_duplicates().tolist()

    if len(symbole) > 1:
        print("Mehrere Aktien passen:")
        for i, symbol in enumerate(symbole, start=1):
            name = treffer.loc[
                treffer["Symbol"] == symbol, "Name"
            ].iloc[0]
            print(f"{i}: {name} ({symbol})")

        auswahl = input("Nummer auswählen (X = zurück): ").strip()

        if auswahl.upper() == "X":
            return

        try:
            symbol = symbole[int(auswahl) - 1]
        except (ValueError, IndexError):
            print("Ungültige Auswahl.")
            return
    else:
        symbol = symbole[0]

    print("\nZeitraum auswählen:")
    print("W   = letzte 7 Tage")
    print("M   = aktueller Monat")
    print("J   = aktuelles Jahr")
    print("90  = letzte 90 Tage")       # NEU
    print("365 = letzte 365 Tage")
    print("X   = zurück")

    zeitraum = input("Ihre Auswahl: ").strip().upper()

    heute = date.today()

    if zeitraum == "X":
        return
    elif zeitraum == "W":
        start = heute - timedelta(days=6)
    elif zeitraum == "M":
        start = heute.replace(day=1)
    elif zeitraum == "J":
        start = heute.replace(month=1, day=1)
    elif zeitraum == "90":                   # NEU
        start = heute - timedelta(days=89)   # NEU
    elif zeitraum == "365":
        start = heute - timedelta(days=364)
    else:
        print("Ungültige Auswahl.")
        return

    daten = df[df["Symbol"] == symbol].copy()

    daten["Datum"] = pd.to_datetime(daten["Datum"], errors="coerce")
    daten = daten.dropna(subset=["Datum", "Kurs"])

    daten = daten[
        daten["Datum"].dt.date >= start
    ]

    daten = daten[
        daten["Datum"].dt.date <= heute
    ]

    # An einem Wochenende können mehrere Abfragen
    # denselben letzten Handelstag enthalten.
    daten = (
        daten.sort_values("Abfragedatum")
        .drop_duplicates(subset="Datum", keep="last")
        .sort_values("Datum")
    )

    if daten.empty:
        print("Für diesen Zeitraum liegen keine Kurse vor.")
        return

    name = daten["Name"].iloc[-1]
    waehrung = daten["Währung"].iloc[-1]

    plt.figure(figsize=(10, 5))

    plt.plot(
        daten["Datum"],
        daten["Kurs"],
        marker="o",
        linestyle="-"
    )

    plt.title(f"{name} ({symbol}) – Kursentwicklung")
    plt.xlabel("Datum")
    plt.ylabel(f"Kurs in {waehrung}")
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()



# ============================================================
# 9. Hauptmenü
# ============================================================

def hauptmenue(df):

    while True:

        print("\n" + "=" * 45)
        print("             AKTIENPROGRAMM")
        print("=" * 45)
        print("1 - Alle hinterlegten Aktien anzeigen")
        print("2 - Neue Aktie hinzufügen")
        print("3 - Kursdiagramm erstellen")
        print("4 - Historische Kurse (tabellarisch)")
        print("5 - Historische Kurse aller Aktien vervollständigen")
        print("6 - Quartalsübersicht in der Konsole ausgeben")
        print("9 - Programm beenden")

        auswahl = input("Bitte Auswahl eingeben: ").strip()

        if auswahl == "1":
            aktien_anzeigen(df)

        elif auswahl == "2":
            df = aktie_hinzufuegen(df)

        elif auswahl == "3":
            kursdiagramm(df)

        elif auswahl == "4":
            historische_kurse(df)

        elif auswahl == "5":
            df = alle_historischen_kurse_auffuellen(df)

        elif auswahl == "6":
            quartalsuebersicht_konsole(df)
        elif auswahl == "9":
            datei_speichern(df)
            print("Daten gespeichert. Programm wird beendet.")
            break

        else:
            print("Ungültige Eingabe. Bitte eine gültige Menüzahl eingeben.")

# ============================================================
# 9. Programmstart
# ============================================================

if __name__ == "__main__":

    df = datei_laden()

    # Erst vorhandene Kurse aktualisieren
    df = kurse_aktualisieren(df)

    # Anschließend Hauptmenü starten
    hauptmenue(df)