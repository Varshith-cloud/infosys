import textstat

class ReadabilityAnalyzer:
    def __init__(self, text):
        self.text = text
        self.num_sentences = textstat.sentence_count(text)
        self.num_words = textstat.lexicon_count(text, removepunct=True)
        self.num_syllables = textstat.syllable_count(text)
        self.complex_words = textstat.difficult_words(text)
        self.char_count = textstat.char_count(text)

    def get_all_metrics(self):
        return {
            "Flesch Reading Ease": textstat.flesch_reading_ease(self.text),
            "Flesch-Kincaid Grade": textstat.flesch_kincaid_grade(self.text),
            "SMOG Index": textstat.smog_index(self.text),
            "Gunning Fog": textstat.gunning_fog(self.text),
            "Coleman-Liau": textstat.coleman_liau_index(self.text)
        }
