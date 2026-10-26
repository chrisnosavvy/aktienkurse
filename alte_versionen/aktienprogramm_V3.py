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

    print(f"\nHole Kursdaten für {symbol} ...")
    df = kurs_speichern(df, symbol)

    return df



# ============================================================
# 7. Kursdiagramm erstellen
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
# 8. Hauptmenü
# ============================================================

def hauptmenue(df):

    while True:

        print("\n" + "=" * 45)
        print("             AKTIENPROGRAMM")
        print("=" * 45)
        print("1 - Alle hinterlegten Aktien anzeigen")
        print("2 - Neue Aktie hinzufügen")
        print("3 - Kursdiagramm erstellen")
        print("4 - Programm beenden")

        auswahl = input("Bitte Auswahl eingeben: ").strip()

        if auswahl == "1":
            aktien_anzeigen(df)

        elif auswahl == "2":
            df = aktie_hinzufuegen(df)

        elif auswahl == "3":
            kursdiagramm(df)

        elif auswahl == "4":
            datei_speichern(df)
            print("Daten gespeichert. Programm wird beendet.")
            break

        else:
            print("Ungültige Eingabe. Bitte 1 bis 4 eingeben.")


# ============================================================
# 9. Programmstart
# ============================================================

if __name__ == "__main__":

    df = datei_laden()

    # Erst vorhandene Kurse aktualisieren
    df = kurse_aktualisieren(df)

    # Anschließend Hauptmenü starten
    hauptmenue(df)