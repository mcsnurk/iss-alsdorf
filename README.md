# 🛰️ ISS über Alsdorf – automatisches Kalenderabo

Dieses kleine GitHub-Projekt erzeugt automatisch einen abonnierbaren iCalendar (`.ics`) mit **sichtbaren ISS-Überflügen über Alsdorf (NRW)**.

## Was als „sichtbar“ gilt

Ein Überflug wird nur eingetragen, wenn:

- die ISS mindestens **10° über dem Horizont** steht,
- die ISS von der Sonne beleuchtet wird,
- die Sonne in Alsdorf mindestens **6° unter dem Horizont** steht.

Die Berechnung verwendet Skyfield und aktuelle Bahndaten (TLE) der ISS von CelesTrak.

## Einmalige Einrichtung auf GitHub

1. Bei GitHub ein neues Repository anlegen, z. B. `iss-alsdorf`.
2. Den gesamten Inhalt dieses Ordners in das Repository hochladen.
3. Unter **Settings → Actions → General → Workflow permissions** die Option **Read and write permissions** aktivieren.
4. Unter **Settings → Pages** bei **Build and deployment** auswählen:
   - Source: **Deploy from a branch**
   - Branch: **main**
   - Folder: **/docs**
5. Unter **Actions** den Workflow **Update ISS calendar** einmal manuell über **Run workflow** starten.
6. Nach dem ersten Pages-Deployment ist die Kalenderdatei erreichbar unter:

   `https://DEIN-GITHUB-NAME.github.io/iss-alsdorf/iss-alsdorf.ics`

   Zum Kalenderabonnement kannst du auch verwenden:

   `webcal://DEIN-GITHUB-NAME.github.io/iss-alsdorf/iss-alsdorf.ics`

## Auf dem iPhone abonnieren

**Einstellungen → Apps → Kalender → Kalenderaccounts → Account hinzufügen → Andere → Kalenderabo hinzufügen**

Dort die `webcal://…`-Adresse eintragen.

## Automatische Aktualisierung

GitHub Actions berechnet den Kalender alle **6 Stunden** neu und schreibt jeweils die kommenden **14 Tage** in die ICS-Datei. Der abonnierte Kalender wird vom Endgerät regelmäßig neu geladen.

## Anpassungen

Oben in `generate_calendar.py` kannst du unter anderem ändern:

- `LOOKAHEAD_DAYS = 14` – Vorschauzeitraum
- `MIN_ALTITUDE_DEG = 10.0` – Mindesthöhe
- `SUN_ALTITUDE_MAX_DEG = -6.0` – gewünschte Dunkelheit
- `LAT` / `LON` – Beobachtungsort

Die Termine enthalten eine Erinnerung **10 Minuten vorher**. Ob eine Erinnerung aus einem abonnierten Kalender vom jeweiligen Kalenderclient tatsächlich angezeigt wird, hängt vom Client ab.
