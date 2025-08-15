# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

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
