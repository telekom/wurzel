# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0
# -*- coding: utf-8 -*-

BASIC_TEST_CASES = [
    {"input_text": "Hello world.", "output_sentences": ["Hello world."]},
    {"input_text": "This is a test. It has two sentences.", "output_sentences": ["This is a test.", "It has two sentences."]},
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Are you okay? Yes! I'm fine.",
    #     "output_sentences": [
    #       "Are you okay?",
    #       "Yes!",
    #       "I'm fine."
    #     ]
    #   },
    #   {
    #     "input_text": "Dr. Smith went to Washington. He arrived at 3 p.m. on Jan. 5, 2020. He left at 6 p.m.",
    #     "output_sentences": [
    #       "Dr. Smith went to Washington.",
    #       "He arrived at 3 p.m. on Jan. 5, 2020.",
    #       "He left at 6 p.m."
    #     ]
    #   },
    {
        "input_text": "The U.S. economy grew. The E.U. responded with new rules. NASA launched at 4 a.m.",
        "output_sentences": ["The U.S. economy grew.", "The E.U. responded with new rules.", "NASA launched at 4 a.m."],
    },
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Pi is about 3.14. Euler's number is about 2.71. Version 1.2.3 was released.",
    #     "output_sentences": [
    #       "Pi is about 3.14.",
    #       "Euler's number is about 2.71.",
    #       "Version 1.2.3 was released."
    #     ]
    #   },
    {
        "input_text": "Visit https://example.com/docs/v1.2?lang=en or email support@example.co.uk. Don't split inside URLs or emails.",
        "output_sentences": [
            "Visit https://example.com/docs/v1.2?lang=en or email support@example.co.uk.",
            "Don't split inside URLs or emails.",
        ],
    },
    {
        "input_text": "Wait... are you serious? Yes... totally serious.",
        "output_sentences": ["Wait... are you serious?", "Yes... totally serious."],
    },
    {
        "input_text": '"This is quoted," she said. "Is it clear?" he asked.',
        "output_sentences": ['"This is quoted," she said.', '"Is it clear?" he asked.'],
    },
    {"input_text": "She left (did she?). I think so (probably!).", "output_sentences": ["She left (did she?).", "I think so (probably!)."]},
    {"input_text": "—Really?—Yes. —Okay, let's go.", "output_sentences": ["—Really?—Yes.", "—Okay, let's go."]},
    # TODO fails with current default splitter
    #   {
    #     "input_text": "He holds a Ph.D. in A.I. research. J. R. R. Tolkien wrote The Lord of the Rings.",
    #     "output_sentences": [
    #       "He holds a Ph.D. in A.I. research.",
    #       "J. R. R. Tolkien wrote The Lord of the Rings."
    #     ]
    #   },
    #   {
    #     "input_text": "Items: 1) First sentence. 2) Second sentence. 3) Third sentence.",
    #     "output_sentences": [
    #       "Items: 1) First sentence.",
    #       "2) Second sentence.",
    #       "3) Third sentence."
    #     ]
    #   },
    #   {
    #     "input_text": "Bitte beachten Sie z.B. die Ausnahme; bzw. warten Sie. Das ist alles.",
    #     "output_sentences": [
    #       "Bitte beachten Sie z.B. die Ausnahme; bzw. warten Sie.",
    #       "Das ist alles."
    #     ]
    #   },
    #   {
    #     "input_text": "He whispered, “don’t go.” Then he shouted, “Run!”",
    #     "output_sentences": [
    #       "He whispered, “don’t go.”",
    #       "Then he shouted, “Run!”"
    #     ]
    #   },
    {
        "input_text": "Newlines and    extra   spaces should not matter.\nHere is a new line. \n\nTabs\tsometimes\tappear. Do they break sentences?",  # noqa: E501
        "output_sentences": [
            "Newlines and    extra   spaces should not matter.\n",
            "Here is a new line. \n\n",
            "Tabs\tsometimes\tappear.",
            "Do they break sentences?",
        ],
    },
    {
        "input_text": "Emojis are fine 🙂. So are emoticons ;-). Mixed? Sure!",
        "output_sentences": ["Emojis are fine 🙂.", "So are emoticons ;-).", "Mixed?", "Sure!"],
    },
    {
        "input_text": "The file is at C:\\\\Program Files\\\\MyApp v1.2.3\\\\readme.txt. Do not split inside paths.",
        "output_sentences": ["The file is at C:\\\\Program Files\\\\MyApp v1.2.3\\\\readme.txt.", "Do not split inside paths."],
    },
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Bring paper, pens, etc. Then start. Don’t forget glue, tape, etc.",
    #     "output_sentences": [
    #       "Bring paper, pens, etc.",
    #       "Then start.",
    #       "Don’t forget glue, tape, etc."
    #     ]
    #   },
    #   {
    #     "input_text": "Paragraphs can be long. This one isn’t.\nBut the next paragraph is separate. It still splits correctly.",
    #     "output_sentences": [
    #       "Paragraphs can be long.",
    #       "This one isn’t.\n",
    #       "But the next paragraph is separate.",
    #       "It still splits correctly."
    #     ]
    #   },
    #   {
    #     "input_text": "He said: \"I saw Mr. Brown Jr. today. He looked well.\" Then he left.",
    #     "output_sentences": [
    #       "He said: \"I saw Mr. Brown Jr. today. He looked well.\"",
    #       "Then he left."
    #     ]
    #   },
    #   {
    #     "input_text": "“Multi-sentence quote test.” “Two sentences inside a quote. Right?” End.",
    #     "output_sentences": [
    #       "“Multi-sentence quote test.”",
    #       "“Two sentences inside a quote. Right?”",
    #       "End."
    #     ]
    #   },
    {"input_text": "(Nested punctuation?!). Works, right? Yes.", "output_sentences": ["(Nested punctuation?!).", "Works, right?", "Yes."]},
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Heads up: e.g., i.e., and etc. can be tricky. Don’t split at e.g. or i.e. unless it ends a sentence.",
    #     "output_sentences": [
    #       "Heads up: e.g., i.e., and etc. can be tricky.",
    #       "Don’t split at e.g. or i.e. unless it ends a sentence."
    #     ]
    #   },
    #   {
    #     "input_text": "• Bullet-like lines can be sentences. • They should still split. • Even without numbers.",
    #     "output_sentences": [
    #       "• Bullet-like lines can be sentences.",
    #       "• They should still split.",
    #       "• Even without numbers."
    #     ]
    #   },
    #   {
    #     "input_text": "Prof. Green met with Sen. O'Neil at 10 a.m. They discussed No. 5 on the agenda.",
    #     "output_sentences": [
    #       "Prof. Green met with Sen. O'Neil at 10 a.m.",
    #       "They discussed No. 5 on the agenda."
    #     ]
    #   },
    {
        "input_text": "She said 'Go now!' and left. 'Really?' he asked.",
        "output_sentences": ["She said 'Go now!' and left.", "'Really?' he asked."],
    },
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Some sentences end without punctuation\nlike this line\nbut your splitter may treat newlines as boundaries.",
    #     "output_sentences": [
    #       "Some sentences end without punctuation",
    #       "like this line",
    #       "but your splitter may treat newlines as boundaries."
    #     ]
    #   },
    {
        "input_text": "Legal style: Smith v. Jones, Inc. was decided. The court adjourned at 5 p.m.",
        "output_sentences": ["Legal style: Smith v. Jones, Inc. was decided.", "The court adjourned at 5 p.m."],
    },
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Ellipses within a sentence... shouldn’t always split unless followed by a capital. But here it does. See?",
    #     "output_sentences": [
    #       "Ellipses within a sentence... shouldn’t always split unless followed by a capital.",
    #       "But here it does.",
    #       "See?"
    #     ]
    #   }
]

REGEX_TEST_CASES = [
    {
        "input_text": "Dr. Smith went to Washington. He arrived at 3.14 p.m. Amazing!",
        "output_sentences": ["Dr. Smith went to Washington.", "He arrived at 3.14 p.m.", "Amazing!"],
    },
    # TODO fails with current default splitter
    # {
    #     "input_text": "He said, \"It's done.\" But was it?",
    #     "output_sentences": [
    #         "He said, \"It's done.\"",
    #         "But was it?"
    #     ]
    # },
    # {
    #     "input_text": "E.g. consider U.S. policy... It changed.",
    #     "output_sentences": [
    #         "E.g. consider U.S. policy...",
    #         "It changed."
    #     ]
    # },
    {
        "input_text": "A. B. Carter agreed. No. 5 was the winning ticket.",
        "output_sentences": ["A. B. Carter agreed.", "No. 5 was the winning ticket."],
    },
    {
        "input_text": "She left in Sept. 2020. Then, in Oct., she returned.",
        "output_sentences": ["She left in Sept. 2020.", "Then, in Oct., she returned."],
    },
    {"input_text": "Hello..!   World.", "output_sentences": ["Hello..!", "World."]},
]

DE_TEST_CASES = [
    {"input_text": "Hallo Welt.", "output_sentences": ["Hallo Welt."]},
    {
        "input_text": (
            "Besuchen Sie https://example.com/docs/v1.2?lang=en oder schreiben Sie an support@example.co.uk. "
            "In URLs oder E-Mails sollte nicht getrennt werden."
        ),
        "output_sentences": [
            "Besuchen Sie https://example.com/docs/v1.2?lang=en oder schreiben Sie an support@example.co.uk.",
            "In URLs oder E-Mails sollte nicht getrennt werden.",
        ],
    },
    {
        "input_text": "„Das ist ein Zitat“, sagte sie. „Ist es klar?“, fragte er.",
        "output_sentences": ["„Das ist ein Zitat“, sagte sie.", "„Ist es klar?“, fragte er."],
    },
    {
        "input_text": "Warte... meinst du das ernst? Ja... völlig ernst.",
        "output_sentences": ["Warte... meinst du das ernst?", "Ja... völlig ernst."],
    },
    {
        "input_text": "Emojis sind okay 🙂. Auch Emoticons ;-). Gemischt? Klar!",
        "output_sentences": [
            "Emojis sind okay 🙂.",
            "Auch Emoticons ;-).",
            "Gemischt?",
            "Klar!",
        ],
    },
]

HR_TEST_CASES = [
    {"input_text": "Pozdrav svijete.", "output_sentences": ["Pozdrav svijete."]},
    # TODO fails with current default splitter
    # {
    #     "input_text": (
    #         "Posjetite https://example.com/docs/v1.2?lang=en ili pišite na support@example.co.uk. "
    #         "U URL-ovima ili e-mail adresama ne bi trebalo dijeliti."
    #     ),
    #     "output_sentences": [
    #         "Posjetite https://example.com/docs/v1.2?lang=en ili pišite na support@example.co.uk.",
    #         "U URL-ovima ili e-mail adresama ne bi trebalo dijeliti.",
    #     ],
    # },
    {
        "input_text": "„Ovo je citat“, rekla je. „Je li jasno?“, upitao je.",
        "output_sentences": ["„Ovo je citat“, rekla je.", "„Je li jasno?“, upitao je."],
    },
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Čekaj... misliš li ozbiljno? Da... potpuno ozbiljno.",
    #     "output_sentences": [
    #       "Čekaj... misliš li ozbiljno?",
    #       "Da... potpuno ozbiljno."
    #     ]
    #   },
    {
        "input_text": "Emojiji su u redu 🙂. Isto vrijedi i za emotikone ;-). Pomiješano? Naravno!",
        "output_sentences": ["Emojiji su u redu 🙂.", "Isto vrijedi i za emotikone ;-).", "Pomiješano?", "Naravno!"],
    },
]

PL_TEST_CASES = [
    {"input_text": "Witaj świecie.", "output_sentences": ["Witaj świecie."]},
    # TODO fails with current default splitter
    # {
    #     "input_text": (
    #         "Odwiedź https://example.com/docs/v1.2?lang=en lub napisz na support@example.co.uk. "
    #         "W adresach URL ani e-mailach nie należy dzielić zdań."
    #     ),
    #     "output_sentences": [
    #         "Odwiedź https://example.com/docs/v1.2?lang=en lub napisz na support@example.co.uk.",
    #         "W adresach URL ani e-mailach nie należy dzielić zdań.",
    #     ],
    # },
    {
        "input_text": "„To jest cytat”, powiedziała. „Czy to jasne?”, zapytał.",
        "output_sentences": ["„To jest cytat”, powiedziała.", "„Czy to jasne?”, zapytał."],
    },
    {
        "input_text": "Czekaj... mówisz poważnie? Tak... całkiem poważnie.",
        "output_sentences": ["Czekaj... mówisz poważnie?", "Tak... całkiem poważnie."],
    },
    {
        "input_text": "Emoji są w porządku 🙂. Podobnie emotikony ;-). Mieszane? Oczywiście!",
        "output_sentences": ["Emoji są w porządku 🙂.", "Podobnie emotikony ;-).", "Mieszane?", "Oczywiście!"],
    },
]

EL_TEST_CASES = [
    {"input_text": "Γειά σου κόσμε.", "output_sentences": ["Γειά σου κόσμε."]},
    # TODO fails with current default splitter
    #   {
    #     "input_text": ("Επισκεφθείτε https://example.com/docs/v1.2?lang=en ή γράψτε στο support@example.co.uk. "
    #                    "Δεν πρέπει να γίνεται διαχωρισμός μέσα σε URL ή e-mail."),
    #     "output_sentences": [
    #       "Επισκεφθείτε https://example.com/docs/v1.2?lang=en ή γράψτε στο support@example.co.uk.",
    #       "Δεν πρέπει να γίνεται διαχωρισμός μέσα σε URL ή e-mail."
    #     ]
    #   },
    {
        "input_text": "«Αυτό είναι ένα απόσπασμα», είπε. «Είναι σαφές;», ρώτησε.",
        "output_sentences": ["«Αυτό είναι ένα απόσπασμα», είπε.", "«Είναι σαφές;», ρώτησε."],
    },
    {
        "input_text": "Περίμενε... μιλάς σοβαρά; Ναι... απολύτως σοβαρά.",
        "output_sentences": ["Περίμενε... μιλάς σοβαρά;", "Ναι... απολύτως σοβαρά."],
    },
    # TODO fails with current default splitter
    #   {
    #     "input_text": "Τα emoji είναι εντάξει 🙂. Το ίδιο και τα emoticons ;-). Μικτά; Φυσικά!",
    #     "output_sentences": [
    #       "Τα emoji είναι εντάξει 🙂.",
    #       "Το ίδιο και τα emoticons ;-).",
    #       "Μικτά;",
    #       "Φυσικά!"
    #     ]
    #   }
]
