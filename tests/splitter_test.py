# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

import mdformat
import pytest

from wurzel.datacontract import MarkdownDataContract
from wurzel.steps.splitter import SimpleSplitterStep
from wurzel.utils.semantic_splitter import (
    SemanticSplitter,
    _get_token_len,
)


@pytest.fixture(scope="function")
def Splitter(env):
    yield SemanticSplitter()


def test_splitter(Splitter):
    text = """# PurpureusTV Fehlercode F30102

#### Eine Anmeldung ist nicht m\u00f6glich.

Wenden Sie sich mit dem Stichwort \"St\u00f6rung\" an unser [Service-Team](/kontakt \"Kontakt\")."""
    contract = MarkdownDataContract(
        md=text,
        keywords="PurpureusTV Fehlercode F30102",
        url="https://www.lorem-ipsum.com/aviar/geraete-zubehoer/magenta-tv-geraete/fehlercodes",
    )

    result = Splitter.split_markdown_document(contract)[0].md
    assert result == text, "Short Document should stay the same"


def test_spliitter_only_header(Splitter):
    text = """# PurpureusTV Fehlercode F30102

#### Eine Anmeldung ist nicht m\u00f6glich."""
    contract = MarkdownDataContract(
        md=text,
        keywords="PurpureusTV Fehlercode F30102",
        url="https://www.lorem-ipsum.com/aviar/geraete-zubehoer/magenta-tv-geraete/fehlercodes",
    )

    result = Splitter.split_markdown_document(contract)[0].md
    assert result == text, "also very short Document should stay the same"


def test_split_markdown_document(Splitter):
    text = """Grundsätzlich erfordern unterschiedliche Fehler unterschiedliche Lösungsansätze.
Wie bei allen elektronischen Geräten, hilft oftmals aber schon ein einfacher Neustart indem Sie das Gerät für 10 Sekunden vom Strom trennen.
Sollte dies nicht helfen, haben wir einige Fehlerbilder und hilfreiche Schritte für Sie zusammengefasst.
[Fehlermeldungen und Hilfestellung](https://www.lorem-ipsum.com/faq/entry/%7Emagenta-tv%7Eerste-hilfe/%7Etvbox_fehlermeldung%7Emaster)
Die Box lässt sich nicht einschalten
Überprüfen Sie, ob das Netzteil/Stromkabel an der Box und der Steckdose fest angeschlossen ist.
Stellen Sie sicher, dass der Schalter auf der Rückseite der HD Box (DVR) bzw. des TV HD Recorders auf **ON** gestellt ist.
Kein Bild bzw. Ton am TV Gerät
Überprüfen Sie, ob das HDMI bzw. SCART Kabel richtig angeschlossen ist.
Überprüfen Sie die Verbindung zwischen der Box und der Dose.
Falls ein zusätzliches Audiogerät angeschlossen ist, überprüfen Sie auch diese Verbindung.
Prüfen Sie bei Tonproblemen ggf. ob der Ton auf dem TV Gerät stumm geschalten ist.
Die Fernbedienung reagiert nicht
Überprüfen Sie, ob die Batterien leer sind und tauschen Sie diese gegebenenfalls.
**Tipp**: Eventuell ist die Fernbedienung nicht mehr mit der Box gekoppelt. Koppeln Sie die Fernbedienung erneut mit der Box um diese bedienen zu können.
Warum ändert sich die Lautstärke beim Wechseln eines Senders?
Hierbei kommt es darauf an, welches Audioformat vom jeweiligen Sender mitgeschickt wird. Seit der Einführung von HD Sendern wird der Ton auf einigen HD Sendern primär in Dolby Digital übermittelt. Beim Wechsel auf SD Sender passiert also auch ein Wechsel des Tonformats und ggf. der Lautstärke.
Eine direkte Lautstärkeregelung des TV HD Recorders ist nicht möglich, da hier der Laustärkepegel so weitergeleitet wird, wie er vom Sender zur Verfügung gestellt wird. Darauf hat Purpureus keinen Einfluss.
TV HD Recorder Lautstärke
## Neuer Mock absatz
![TV HD Recorder]( "TV HD Recorder - Gerät")
Um die Lautstärke schnell anpassen zu können, empfehlen wir Ihnen die Purpureus Fernbedienung\xa0mit Ihrem TV Gerät zu koppeln.
Es gibt zudem die Möglichkeit in den Ton & Bild Einstellungen die Dolby Audioausgabe zu deaktivieren und die Stereoausgabe zu aktivieren. Anschließend wird alles in Stereo ausgegeben, sodass sich keine Lautstärkesprünge mehr ergeben.
![Dolby Digital]( "Entertain Box 4K - Dolby Einstellungen")
[Öffnet in neuem Fenster
Purpureus Fernbedienung mit TV Gerät koppeln](https://www.lorem-ipsum.com/hilfe-service/services/hardwaresupport/topic/erste-schritte/fernbedienung-mit-tv-koppeln)
[Öffnet in neuem Fenster
Hilfestellung bei Fehlermeldung Signalverlust oder Standbildern](https://www.lorem-ipsum.com/faq/entry/%7Emagenta-tv%7Eerste-hilfe/%7EHilfe_Fehler_Signalverlust%7Emaster)
[Öffnet in neuem Fenster
Sender fehlen oder werden übersprungen](https://www.lorem-ipsum.com/faq/entry/%7Emagenta-tv%7Eerste-hilfe/%7ESender_fehlen%7Emaster)
![TV HD Recorder]( "TV HD Recorder - Gerät")
TV HD Recorder
[Öffnet in neuem Fenster
TV HD Recorder Fehlerbehebung](https://www.lorem-ipsum.com/faq/entry/%7Emagenta-tv%7Eerste-hilfe/%7ETVHD_Recorder_Behebung%7Emaster)
"""

    contract = MarkdownDataContract(
        md=text,
        keywords="TV Fehlerbehebung",
        url="https://www.lorem-ipsum.com/hilfe-service/faq/_jcr_content/root/container_750332750/faq.entry.%7Emagenta-tv%7Eerste-hilfe.%7ETV_Fehlerbehebung%7Emaster.html",
    )

    result = Splitter.split_markdown_document(contract)
    assert len(result) > 1
    assert "TV HD Recorder Fehlerbehebun" in result[-1].md


def test_sentence_splitter(Splitter):
    # @Thomas inkonsitenz mit token_limit, buffer
    text = "Mein Name ist Manfred. Ich bin am rande der Welt angekommen. Wir sind mit Mr. Bean unterwegs. Dabei haben wir Heute ein Kanninchen adoptiert und sind damit zum Mond geflogen. Auf dessen Rückseite haben wir dann Karotten geerntet und sind damit auf dem Rücken eines Schweins zurück zum Mars gefolgen. "
    chunks = SemanticSplitter(token_limit=20, token_limit_buffer=3)._split_by_sentence(
        text
    )
    assert len(chunks) == 3
    assert "Mein Name ist Manfred." in chunks[0]
    assert all(chunk for chunk in chunks)
    assert "auf dem Rück" in chunks[-1]
    assert (
        abs(_get_token_len(text) - sum(_get_token_len(chunk) for chunk in chunks)) < 19
    )


def test_sentence_splitter2(Splitter):
    text = '* [Öffnet in neuem Fenster\n  Wlan optimieren](https://www.lorem-ipsum.com/wlan-optimieren#konfiguriert)\n* [Öffnet in neuem Fenster\n  Hardware Support](https://www.lorem-ipsum.com/hilfe-service/services/hardwaresupport)\n  Überlagerte WLAN Kanäle\n  Damit Ihre drahtlosen Geräte mit Highspeed unterwegs sind, empfehlen wir Ihnen, den verwendeten WLAN Kanal regelmäßig zu ändern. Wie das geht, zeigt Ihnen unser\xa0[Hardware Support](https://www.lorem-ipsum.com/hilfe-service/services/hardwaresupport/).\n  Standardmäßig können die meisten Modem/Router den optimalen Kanal selbständig feststellen und konfigurieren.\n  In manchen Fällen ist es allerdings ratsam, den Kanal manuell zu optimieren.\n  Nachfolgend finden Sie eine Schritt-für-Schritt Anleitung für die Internet Fiber Box. Weitere Anleitungen finden Sie in unserem\xa0Hardwaresupport.\n  Wie ändere ich den WLAN Kanal auf meiner Internet Fiber Box?\n  Schritt 1:  \n  Öffnen Sie Ihren Browser und öffnen Sie die Seite 192.168.0.1.\n  Sie werden nun nach dem Passwort des Modems gefragt. Falls Sie dieses nicht geändert haben, finden Sie es auf der Unterseite des Modems. Geben Sie dieses in das dafür vorgesehene Feld ein und klicken Sie auf "Weiter".\n  ![Fiber_Box_Anmeldung]( "Fiber Box - Anmeldung Web Interface")\n  Schritt 2:  \n  Wählen Sie links im Menü\xa0"Erweiterte Einstellungen" -> "WLAN"\xa0und danach\xa0"WLAN Signal".\n  Sollten Sie WLAN Kanal-Optimierung aktiviert haben, schalten Sie diese bitte aus.\n  Setzen Sie nun ein Häkchen bei "Manuell" – das können Sie sowohl bei 2,4 GHz als auch bei 5 GHz getrennt konfigurieren.\n  Klicken Sie anschließend rechts auf den aktuellen Kanal und wählen Sie aus der Liste den gewünschten Kanal aus und bestätigen Sie die Einstellungen mit\xa0"Änderungen übernehmen".\n  Wenn Sie nicht wissen, welcher der optimale Kanal für Ihren Standort ist, testen Sie einfach einen Kanal nach dem anderen aus.  \n  Prüfen Sie dann mit welchem Kanal der Empfang am besten bzw. am stabilsten ist.\n  ![Erweiterte Einstellungen]( "Fiber Box - WLAN optimieren")\n  Frequenzband 2,4 GHz oder 5 GHz\n  Ein Frequenzband bezeichnet einen bestimmten Frequenzbereich, auf dem Signale gesendet werden können.\n  WLAN Wellen können über die beiden Frequenzbänder 2.4 GHz (GHz = Gigahertz) und 5 GHz übertragen werden.\n  Diese unterscheiden sich in der Geschwindigkeit und Distanz. Das 2.4 GHz Netz strahlt weiter, ist dafür aber langsamer.\n  Das 5 GHz Netz hingegen ist schneller, funkt aber nicht so weit.\n  In der Regel ist das 5 GHz Netz weniger belegt und bietet deshalb eine bessere Verbindung.\n  2,4 GHz bzw. 5 GHz umbenennen auf der Internet Fiber Box\n  Schritt 1:  \n  Öffnen Sie Ihren Browser und öffnen Sie die Seite **192.168.0.1**.\n  Sie werden nun nach dem Passwort des Modems gefragt. Falls Sie dieses nicht geändert haben, finden Sie es auf der Unterseite des Modems.   \n  Geben Sie dieses in das dafür vorgesehene Feld ein und klicken Sie auf "Weiter".\n  ![Login]( "Fiber Box - Anmeldung Web Interface")\n  Schritt 2:  \n  Sie sehen nun die Startseite der Internet Fiber Box.\n  Wählen Sie links im Menü "Erweiterte Einstellungen".\n  Öffnen Sie dann "WLAN" und danach "Sicherheit".\n  Ändern Sie den Namen des 2,4 GHz bzw. des 5 GHz Netzes und bestätigen Sie die Eingabe mit "Änderungen übernehmen".\n  ![Erweiterte Einstellungen]( "Fiber Box - SSID/WLAN Namen ändern")\n  Standort des Modems/Routers\n  Platzieren Sie ihr WLAN Modem/ihren WLAN Router idealerweise leicht erhöht, damit es über Möbel und andere Hindernisse hinwegkommt.  \n  Das Gerät funktioniert am besten, wenn es frei steht und nicht in einer Schublade oder hinter einem Wandverbau versteckt wird.\n  Bei größeren Wohnungen bzw. Häusern, sowie der Nutzung von WLAN über mehrere Stockwerke, kann der Einsatz von zusätzlicher WLAN Hardware notwendig sein.  \n  Nähere Informationen entnehmen Sie der FAQ zu [WLAN Empfang erweitern](https://www.lorem-ipsum.com/faq/entry/%7Etechnische-anfrage%7Emobiles-internet%7Ewlan/%7EWlan_Empfang_erweitern%7Emaster).\n  Beachten Sie bei der Platzierung Ihrer Internet Flex Box/Ihres Internet Flex Routers auch die [Platzierung für einen optimalen LTE Empfang](https://www.lorem-ipsum.com/faq/entry/%7Etechnische-anfrage%7Emobiles-internet%7Eerste-hilfe/%7EInternetFlex_Empfang_Position_Box_Router%7Emaster).\n  Alte Geräte im WLAN\n  Wenn Sie ältere Geräte in Ihr WLAN einbinden, die den sogenannten N-Standard nicht unterstützen (wie z.B. das iPhone 3, das Samsung Galaxy GT-i7500, die PlayStation 3 sowie alle Geräte, die vor 2009 auf den Markt kamen), behindern diese die Leistung aller Geräte im gleichen Netz.\n  Vermeiden von Störquellen\n  Ihr Modem/Router ist gerne für sich. Folgende Geräte sollten ihm nicht zu nahe kommen, denn sie können die Qualität Ihrer drahtlosen Internetverbindung beeinträchtigen.\n* Basisstation des Schnurlos Telefons\n* Babyphone\n* Mikrowelle\n* Bluetooth-Geräte\n* Fernsehgerät\n* A/V Receiver\n* HiFi Lautsprecher\n'
    chunks = Splitter._split_by_sentence(text)
    assert "Überlagerte WLAN Kanäle" in chunks[0]
    assert all(chunk for chunk in chunks)
    assert "HiFi Lautsprecher" in chunks[-1]
    assert (
        abs(_get_token_len(text) - sum(_get_token_len(chunk) for chunk in chunks)) > 3
    )


def test_splitter_header_breadcrum(Splitter):
    text = '### Erste Hilfe\n#### Purpureus TV Box/TV HD Recorder auf Werkseinstellungen zurücksetzen\nIn manchen Fällen kann es sinnvoll sein die Box auf die Werkseinstellungen zurück zu setzen.\nWie Sie dies veranlassen können, erklären wir Ihnen hier.\nBitte beachten Sie, dass Sie anschließend die Ersteinrichtung erneut durchlaufen lassen und es erforderlich ist, Funktionen, wie die persönlichen Empfehlungen, wieder einzurichten.\n![Purpureus TV Box]( "Purpureus TV Box - Gerät")\nPurpureus TV Box\n[Öffnet in neuem Fenster\nAnleitung im Hardwaresupport](https://www.lorem-ipsum.com/hilfe-service/services/hardwaresupport/device/magenta-tv/box/topic/einstellungen/magenta-tv-zurucksetzen/1)\nWenn Sie die Werkseinstellungen der Purpureus TV Box wieder herstellen möchten, wechseln Sie über die "**Home**" Taste in das Hauptmenü und öffnen Sie anschließend die Einstellungen.\nWählen Sie nun\xa0**Geräte/Google-Einstellungen – Geräte-Einstellungen – Info – Auf Werkseinstellungen zurücksetzen**.\nUm den Vorgang zu starten wählen Sie erneut "Auf Werkseinstellungen z**urücksetzen**" und anschließend "Alles löschen".\nDie Box startet sich anschließend neu und stellt die werkseitigen Einstellungen wieder her.\n![Purpureus TV Box - Werkseinstellungen]( "TV Box - Werkseinstellungen Android TV 12")\nTV HD Recorder zurücksetzen\n![TV HD Recorder]( "TV HD Recorder - Gerät")\nWenn Sie die Werkseinstellungen des TV HD Recorders wieder herstellen möchten, navigieren Sie über die "**Menü**" Taste Ihrer Fernbedienung zum Einstellungsrad.\nGehen Sie hier über die Pfeiltasten weiter zum Menüpunkt "**System**" und wählen Sie "**Auf Werkseinstellungen zurücksetzen**".\nGeben Sie dann Ihren vierstelligen TV PIN Code ein.\nNun können Sie die Box auf die Werkseinstellungen zurücksetzen.\n**Hinweis**:\xa0Sie im Zuge des Zurücksetzens die Möglichkeit gespeicherte Aufnahmen zu behalten oder zu löschen.\n![TV HD Recorder - Werkseinstellungen]( "TV HD Recorder - Werkseinstellungen")\n'
    md = MarkdownDataContract(
        md=text,
        url="https://www.lorem-ipsum.com/hilfe-service/faq/_jcr_content/root/container_750332750/faq.entry.%7Emagenta-tv%7Eerste-hilfe.%7EPurpureusTV-Werkseinstellungen%7Emaster.html",
        keywords="Purpureus TV Box/TV HD Recorder auf Werkseinstellungen zurücksetzen",
    )
    chunks = Splitter.split_markdown_document(md)
    assert len(chunks) == 2, "split into two"
    assert "In manchen Fällen kann es sinnvoll" in chunks[0].md
    # assert "Erste Hilfe" in chunks[0].keywords
    assert "Aufnahmen zu behalten oder zu löschen" in chunks[-1].md
    # assert "Erste Hilfe" in chunks[-1].keywords


#### Testcases
test_case_1 = """# Heading 1
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean ut venenatis neque. Aliquam sagittis sit amet velit sit amet dictum. Etiam nec porttitor quam. Sed felis mi, auctor ac lacus vel, maximus varius nulla. Sed ornare lectus id risus ornare euismod. Curabitur at aliquet justo, non vestibulum magna. Phasellus sagittis eu lorem sit amet vestibulum.

## Heading 2
Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh. Proin felis lorem, fermentum auctor sem a, imperdiet viverra augue. Duis porta a justo accumsan laoreet. Cras eleifend consectetur lectus sed accumsan. Duis accumsan volutpat lectus, nec rhoncus magna vehicula sit amet. Integer dapibus venenatis risus ut blandit. Mauris semper bibendum maximus. Suspendisse blandit quis urna non ultricies. Morbi tellus risus, tincidunt nec egestas quis, pellentesque sed nibh."""

test_case_1_result = [
    """# Heading 1

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean ut venenatis neque. Aliquam sagittis sit amet velit sit amet dictum. Etiam nec porttitor quam. Sed felis mi, auctor ac lacus vel, maximus varius nulla. Sed ornare lectus id risus ornare euismod. Curabitur at aliquet justo, non vestibulum magna. Phasellus sagittis eu lorem sit amet vestibulum.""",
    """# Heading 1

## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh. Proin felis lorem, fermentum auctor sem a, imperdiet viverra augue. Duis porta a justo accumsan laoreet. Cras eleifend consectetur lectus sed accumsan. Duis accumsan volutpat lectus, nec rhoncus magna vehicula sit amet. Integer dapibus venenatis risus ut blandit. Mauris semper bibendum maximus. Suspendisse blandit quis urna non ultricies""",
]

#### TESTCASE 2
test_case_2 = """
### Erhöhen Sie die Reichweite Ihres WLAN.

Mit unseren modernen [Mesh-WLAN](/hilfe/geraete-zubehoer/heimnetzwerk-powerline-wlan/speed-home-wlan/wlan-mesh-was-ist-das) Geräten erschaffen Sie ein WLAN, das bis in den letzten Winkel reicht und für optimale Geschwindigkeit sorgt. Unsere [Speed Home WiFi](https://www.example.com/sample-data/geraete/wlan-und-router/speed-home-wifi) Geräte unterstützen Mesh-WLAN und können im Gegensatz zu herkömmlichen Techniken große Wohnflächen und mehrere Etagen versorgen. Für das beste WLAN-Erlebnis empfehlen wir den [Speed Home WiFi](https://www.example.com/sample-data/geraete/wlan-und-router/speed-home-wifi) in Verbindung mit einem [Speedport Smart 3](https://www.example.com/sample-data/geraete/wlan-und-router/speedport-smart-3). Gerne unterstützen wir Sie auch mit einer individuellen Beratung.Zusammen finden wir die Lösung für Ihr ideales Heimnetz. [Beratung Heimnetzwerk](http://www.example.com/zuhause/tarife-und-optionen/zubuchoptionen/beratung-heimnetz)"""

test_case_2_result = [
    """### Erhöhen Sie die Reichweite Ihres WLAN.\n\nMit unseren modernen [Mesh-WLAN](/hilfe/geraete-zubehoer/heimnetzwerk-powerline-wlan/speed-home-wlan/wlan-mesh-was-ist-das) Geräten erschaffen Sie ein WLAN, das bis in den letzten Winkel reicht und für optimale Geschwindigkeit sorgt. Unsere [Speed Home WiFi](https://www.example.com/sample-data/geraete/wlan-und-router/speed-home-wifi) Geräte unterstützen Mesh-WLAN und können im Gegensatz zu herkömmlichen Techniken große Wohnflächen und mehrere Etagen versorgen. Für das beste WLAN-Erlebnis empfehlen wir den [Speed Home WiFi](https://www.example.com/sample-data/geraete/wlan-und-router/speed-home-wifi) in Verbindung mit einem [Speedport Smart 3](https://www.example.com/sample-data/geraete/wlan-und-router/speedport-smart-3). Gerne unterstützen wir Sie auch mit einer individuellen Beratung.Zusammen finden wir die Lösung für Ihr ideales Heimnetz. \\[Beratung Heimnetzwerk"""
]

#### TESTCASE 3

test_case_3 = """# Heading 1
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean ut venenatis neque. Aliquam sagittis sit amet velit sit amet dictum. Etiam nec porttitor quam. Sed felis mi, auctor ac lacus vel, maximus varius nulla. Sed ornare lectus id risus ornare euismod. Curabitur at aliquet justo, non vestibulum magna. Phasellus sagittis eu lorem sit amet vestibulum.

# Heading 1
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean ut venenatis neque. Aliquam sagittis sit amet velit sit amet dictum. Etiam nec porttitor quam. Sed felis mi, auctor ac lacus vel, maximus varius nulla. Sed ornare lectus id risus ornare euismod. Curabitur at aliquet justo, non vestibulum magna. Phasellus sagittis eu lorem sit amet vestibulum.

## Heading 2
Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac bibendum tincidunt nibh."""

# Hard cut over token len
test_case_3_result = [
    """# Heading 1
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean ut venenatis neque. Aliquam sagittis sit amet velit sit amet dictum. Etiam nec porttitor quam. Sed felis mi, auctor ac lacus vel, maximus varius nulla. Sed ornare lectus id risus ornare euismod. Curabitur at aliquet justo, non vestibulum magna. Phasellus sagittis eu lorem sit amet vestibulum.""",
    """# Heading 1
Lorem ipsum dolor sit amet, consectetur adipiscing elit. Aenean ut venenatis neque. Aliquam sagittis sit amet velit sit amet dictum. Etiam nec porttitor quam. Sed felis mi, auctor ac lacus vel, maximus varius nulla. Sed ornare lectus id risus ornare euismod. Curabitur at aliquet justo, non vestibulum magna. Phasellus sagittis eu lorem sit amet vestibulum.

## Heading 2
Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac bib""",
]

### TESTCASE 4

test_case_4 = """# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor."""

# Cut off ""
# Due to too short & next = new paragraph
test_case_4_result = [
    """# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.

Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim,""",
    """# Heading 1

## Heading 2

nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus. Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.""",
]

test_case_5 = """# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.

# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.

# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.

# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor."""

test_case_6 = """# PurpureusZuhause XL Flex
**Internet-Flat** - Download mit bis zu 250 MBit/s und Upload mit bis zu 50 MBit/s
**Telefonie-Flat** - Ins deutsche Fest- und Mobilfunknetz in HD-Voice Qualit\u00e4t telefonieren.

## Preis
* PurpureusZuhause XL Flex kostet monatlich 54,95\u00a0\u20ac.
* Einmaliger Bereitstellungspreis f\u00fcr neuen Telefonanschluss 69,95\u00a0\u20ac.
* Keine Mindestvertragslaufzeit, K\u00fcndigungsfrist 1 Monat.
* PurpureusZuhause XL Flex ist in vielen Anschlussbereichen verf\u00fcgbar.

## Gutschriften
* 100 \u20ac Routergutschrift
* Routergutschrift: Bei Buchung von PurpureusZuhause XL Flex erfolgt eine Routergutschrift i. H. v. 100 \u20ac auf einer der n\u00e4chsten Telekom Rechnungen, bei Miete eines Routers (im Endger\u00e4te-Servicepaket ab mtl. 6,95 \u20ac/Monat, 12 Monate Mindestvertragslaufzeit). Aktion gilt bis 01.07.2024 f\u00fcr Breitband-Neukunden, die in den letzten 3 Monaten keinen Breitbandanschluss bei der Telekom hatten."""
test_case_6_result = [
    """# PurpureusZuhause XL Flex
**Internet-Flat** - Download mit bis zu 250 MBit/s und Upload mit bis zu 50 MBit/s
**Telefonie-Flat** - Ins deutsche Fest- und Mobilfunknetz in HD-Voice Qualit\u00e4t telefonieren.

## Preis
* PurpureusZuhause XL Flex kostet monatlich 54,95\u00a0\u20ac.
* Einmaliger Bereitstellungspreis f\u00fcr neuen Telefonanschluss 69,95\u00a0\u20ac.
* Keine Mindestvertragslaufzeit, K\u00fcndigungsfrist 1 Monat.
* PurpureusZuhause XL Flex ist in vielen Anschlussbereichen verf\u00fcgbar.""",
    """# PurpureusZuhause XL Flex
## Gutschriften
* 100 \u20ac Routergutschrift
* Routergutschrift: Bei Buchung von PurpureusZuhause XL Flex erfolgt eine Routergutschrift i. H. v. 100 \u20ac auf einer der n\u00e4chsten Telekom Rechnungen, bei Miete eines Routers (im Endger\u00e4te-Servicepaket ab mtl. 6,95 \u20ac/Monat, 12 Monate Mindestvertragslaufzeit). Aktion gilt bis 01.07.2024 f\u00fcr Breitband-Neukunden, die in den letzten 3 Monaten keinen Breitbandanschluss bei der Telekom hatten.""",
]

test_case_7 = """Wenn Sie Ihre Rufnummer von einem anderen Anbieter zu Purpureus mitgenommen haben, geben Sie bitte die Nummer der Sprachbox des anderen Anbieters ein.

*   Vorwahl 0650 ( ehemals tele.ring): +43 650 11 Rufnummer
*   Vorwahl 0664 (A1): +43 664 77 Rufnummer
*   Vorwahl 0680 (BOB): +43 680 77 Rufnummer
*   Vorwahl 0688 (BOB): +43 688 85 Rufnummer
*   Vorwahl 0699 (Drei+Orange): die erste Ziffer der Rufnummer wird durch eine 3 ersetzt. (z.B.: aus +43 699 1 123 4567 wird +43 699 3 123 4567)
*   Vorwahl 0660 (Drei): +43 660 33 Rufnummer
*   Vorwahl 0699 (Yess): + 43 699 82 Rufnummer (z.B.: +43 699 82 123 4567)

Weitere Sprachboxnummern

*   Vorwahl 0681 (Yess): zweite Ziffer wird durch eine 1 ersetzt. (z.B.: aus +43681 1 0 345678 wird +43681 1 1 345678)
*   Vorwahl 0699 (Tele2UTA): +43 699 89 Rufnummer (z.B.: +43 699 89 123 4567)
*   Vorwahl 0688 (Tele2UTA): + 43688 85 Rufnummer (z.B.: +43 688 85 123 4567)
*   Vorwahl 0676 (VOL.mobil): +43 676 22 Rufnummer
*   Vorwahl 0677 (HoT): +43 677 60 Rufnummer
*   Vorwahl 0677 (AllianzSIM): +43 677 60 Rufnummer
*   Vorwahl 0678: +43 678 11 Rufnummer
*   Vorwahl 0670 (Spusu): +43 670 90 Rufnummer"""

test_case_7_result = [
    """Wenn Sie Ihre Rufnummer von einem anderen Anbieter zu Purpureus mitgenommen haben, geben Sie bitte die Nummer der Sprachbox des anderen Anbieters ein.

*   Vorwahl 0650 ( ehemals tele.ring): +43 650 11 Rufnummer
*   Vorwahl 0664 (A1): +43 664 77 Rufnummer
*   Vorwahl 0680 (BOB): +43 680 77 Rufnummer
*   Vorwahl 0688 (BOB): +43 688 85 Rufnummer
*   Vorwahl 0699 (Drei+Orange): die erste Ziffer der Rufnummer wird durch eine 3 ersetzt. (z.B.: aus +43 699 1 123 4567 wird +43 699 3 123 4567)
*   Vorwahl 0660 (Drei): +43 660 33 Rufnummer
*   Vorwahl 0699 (Yess): + 43 699 82 Rufnummer (z.B.: +43 699 82 123 4567)
  Weitere Sprachboxnummern""",  # Weitere Sprachboxnummern should be below but cannot be identified as heading
    # Fix linebreak later in markdown renderer
    """
*   Vorwahl 0681 (Yess): zweite Ziffer wird durch eine 1 ersetzt. (z.B.: aus +43681 1 0 345678 wird +43681 1 1 345678)
*   Vorwahl 0699 (Tele2UTA): +43 699 89 Rufnummer (z.B.: +43 699 89 123 4567)
*   Vorwahl 0688 (Tele2UTA): + 43688 85 Rufnummer (z.B.: +43 688 85 123 4567)
*   Vorwahl 0676 (VOL.mobil): +43 676 22 Rufnummer
*   Vorwahl 0677 (HoT): +43 677 60 Rufnummer
*   Vorwahl 0677 (AllianzSIM): +43 677 60 Rufnummer
*   Vorwahl 0678: +43 678 11 Rufnummer
*   Vorwahl 0670 (Spusu): +43 670 90 Rufnummer""",
]

test_case_table = """# Popis satelitskih programa po paketima

Odaberite idealan paket satelitskih programa prema va\u0161im potrebama:

![](\/\/static.hrvatskitelekom.hr\/webresources\/images\/5G\/arrows\/left_active_black.png)
![](\/\/static.hrvatskitelekom.hr\/webresources\/images\/5G\/arrows\/right_active_black.png)

| Osnovni Extra paket | |
| --- | --- |
| 20 | RTLliving |
| 21 | HRT1 |
| 22 | HRT2 |
| 23 | RTL |
| 24 | NOVATV |
| 25 | RTL2 |
| 400 | Arenasport 1 |
| 401 | Arenasport 2 |
| 402 | Arenasport 3 |
| 403 | Arenasport 4 |
| 500 | 24Kitchen |
| 501 | E! |
| 600 | CMC |
| 605 | MTV 00s |
| 606 | MTV 80s |
| 610 | Jugoton |
| 701 | CNN International Europe |
| 901 | BlueHustler |
| 907 | Vivid |
| 850 | Aurora TV |
| 870 | Radio HR1 |
| 872 | bravo! |
| 871 | Radio Otvoreni |
| 882 | Radio Happy FM |
| 873 | Radio Antena |
| 881 | Radio Marija |
| 886 | Radio Enter Zagreb |
| 890 | Radio Katoli\u010dki |

| MAX Arena | |
| --- | --- |
| 34 | MAXSport 1 |
| 402 | Arenasport 3 |
| 403 | Arenasport 4 |
| 404 | Arenasport 5 |
| 405 | Arenasport 6 |
| 406 | MAXSport 2 |

| MAX Arena 2 | |
| --- | --- |
| 406 | MAXSport 2 |
| 417 | Arenasport 7 |
| 418 | Arenasport 8 |
| 419 | Arenasport 9 |
| 420 | Arenasport 10 |

| MAX Sport Plus | |
| --- | --- |
| 34 | MAXSport 1 |
| 402 | Arenasport 3 |
| 403 | Arenasport 4 |
| 404 | Arenasport 5 |
| 405 | Arenasport 6 |
| 406 | MAXSport 2 |
| 420 | Arenasport 10 |
| 425 | Extreme Sports Channel |
| 516 | Balkan Trip |
| 602 | Club MTV |
| 603 | MTV Hits |
| 604 | Stingray Djazz |
| 902 | Vivid Touch |
| 903 | Vivid Red |
| 904 | Brazzers TV |
| 905 | Hustler TV |
| 906 | Private |
| 907 | Vivid |

| HBO Premium | |
| --- | --- |
| 305 | HBO |
| 306 | HBO 2 |
| 307 | HBO 3 |
| 308 | Cinemax |
| 309 | Cinemax 2 |

| HBO | |
| --- | --- |
| 305 | HBO |
| 306 | HBO 2 |
| 307 | HBO 3 |

| Cinemax | |
| --- | --- |
| 308 | Cinemax |
| 309 | Cinemax 2 |

| Plus paket | |
| --- | --- |
| 602 | Club MTV |
| 603 | MTV Hits |
| 604 | Stingray Djazz |
| 902 | Vivid Touch |
| 903 | Vivid Red |
| 904 | Brazzers TV |
| 905 | Hustler TV |
| 906 | Private |
 """


@pytest.mark.parametrize(
    "input_text, expected_results",
    [
        pytest.param(test_case_1, test_case_1_result, id="Simple Split"),
        pytest.param(
            test_case_2, test_case_2_result, id="Tests: Test Sentence splitter"
        ),
        pytest.param(
            test_case_3,
            test_case_3_result,
            id="Cut to hard token limit due to txoken buffer",
        ),
        # pytest.param(test_case_4, test_case_4_result, id="Problems: clarify cut off"),
        pytest.param(test_case_6, test_case_6_result),
        pytest.param(test_case_7, test_case_7_result),
    ],
)
def test_case(input_text, expected_results, Splitter):
    res = Splitter.split_markdown_document(
        MarkdownDataContract(md=input_text, url="test", keywords="pytest")
    )
    assert len(res) == len(expected_results)
    for x, y in zip(res, expected_results):
        assert x.md == mdformat.text(y).strip(), "got == expected"


def test_table(Splitter):
    res = Splitter.split_markdown_document(
        MarkdownDataContract(md=test_case_table, url="test", keywords="pytest")
    )
    assert len(res) > 1
    assert all(
        phrase in res[-1].md
        for phrase in [
            "Popis satelitskih programa po paketima",
            "Hustler TV ",
            "Plus paket",
        ]
    )
    assert all(
        phrase in res[0].md
        for phrase in [
            "Popis satelitskih programa po paketima",
            "Odaberite idealan paket satelitskih programa prema",
        ]
    )
    assert all(
        phrase in res[1].md
        for phrase in [
            "Popis satelitskih programa po paketima",
            "Osnovni Extra paket",
            "MTV 00s",
        ]
    )


def test_simple_splitter_step(tmp_path):
    test_data = [
        MarkdownDataContract(
            md="""
# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.

# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.

# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.

# Heading 1
## Heading 2

Sed euismod rutrum lorem, nec rutrum dolor accumsan in. In rhoncus urna id augue accumsan tristique. Quisque dictum tincidunt lacus dignissim facilisis. Suspendisse id magna sit amet risus bibendum maximus vel et nisi. Curabitur imperdiet, est ac tristique consectetur, odio ligula molestie nisi, non hendrerit nisl est quis leo. Nulla sagittis orci vel turpis lacinia, ut volutpat turpis tempor. Proin et nisi eget dui ullamcorper finibus. Aenean augue orci, scelerisque sit amet tortor ac, bibendum tincidunt nibh.
Sed sed eros a enim consequat laoreet vitae et justo. Pellentesque eget nisi nec ante viverra aliquet a vel massa. Ut sit amet est sapien. Suspendisse sit amet nisl dui. Fusce posuere diam et condimentum posuere. Ut mattis tempor lorem eget vestibulum. In hac habitasse platea dictumst. Cras facilisis erat consectetur volutpat laoreet. Aenean vitae mattis enim, nec fermentum mi. Orci varius natoque penatibus et magnis dis parturient montes, nascetur ridiculus mus.

Duis consectetur ex elementum arcu volutpat, vitae rutrum risus vehicula. Donec urna lorem, mattis et justo non, interdum blandit odio. Mauris interdum lectus in mauris porta interdum. Maecenas rutrum, tellus vestibulum mattis ultrices, tellus velit iaculis lacus, a tristique orci mauris in orci. Ut eu mauris vel odio fringilla pretium eu vulputate ipsum. In non velit ac ligula scelerisque pharetra. Vestibulum ante ipsum primis in faucibus orci luctus et ultrices posuere cubilia curae; Cras porta iaculis auctor.""",
            url="www.dummy.url/404",
            keywords="preserve me",
        )
    ]

    step = SimpleSplitterStep()
    result = step.run(test_data)
    assert len(result) > 2
    assert isinstance(result[0], MarkdownDataContract)
