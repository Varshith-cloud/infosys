import os
import torch
import streamlit as st
import nltk
from nltk.tokenize import sent_tokenize

try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)

TRANSFORMERS_AVAILABLE = False
BNB_AVAILABLE = False
try:
    from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
    TRANSFORMERS_AVAILABLE = True
    try:
        from transformers import BitsAndBytesConfig
        BNB_AVAILABLE = True
    except ImportError:
        pass
except ImportError as e:
    TRANSFORMERS_AVAILABLE = False

# ─── NLLB Translation Support ───
LANG_CODES = {
    "English": "eng_Latn", "Hindi": "hin_Deva", "Tamil": "tam_Taml",
    "Kannada": "kan_Knda", "Telugu": "tel_Telu", "Marathi": "mar_Deva",
    "Bengali": "ben_Beng"
}

@st.cache_resource(show_spinner=False)
def load_translation_model():
    """Load NLLB-200 distilled model for multilanguage translation"""
    if not TRANSFORMERS_AVAILABLE:
        return None, None
    try:
        model_id = "facebook/nllb-200-distilled-600M"
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForSeq2SeqLM.from_pretrained(model_id, device_map="auto")
        return tokenizer, model
    except Exception as e:
        print(f"Warning: Could not load NLLB translation model: {e}")
        return None, None

def translate_text(text, source_lang="English", target_lang="English"):
    """Translate text between supported languages using NLLB-200"""
    if source_lang == target_lang:
        return text

    trans_tok, trans_model = load_translation_model()
    if trans_tok is None or trans_model is None:
        return text  # fallback: return untranslated

    src_code = LANG_CODES.get(source_lang, "eng_Latn")
    tgt_code = LANG_CODES.get(target_lang, "eng_Latn")

    try:
        # Process in chunks to handle long texts
        sentences = sent_tokenize(text)
        chunks = []
        curr_chunk = []
        curr_len = 0
        for s in sentences:
            s_len = len(s.split())
            if curr_len + s_len > 200 and curr_chunk:
                chunks.append(" ".join(curr_chunk))
                curr_chunk = [s]
                curr_len = s_len
            else:
                curr_chunk.append(s)
                curr_len += s_len
        if curr_chunk:
            chunks.append(" ".join(curr_chunk))

        translated_parts = []
        for chunk in chunks:
            trans_tok.src_lang = src_code
            inputs = trans_tok(chunk, return_tensors="pt", max_length=512, truncation=True).to(trans_model.device)
            tgt_token_id = trans_tok.convert_tokens_to_ids(tgt_code)
            with torch.no_grad():
                outputs = trans_model.generate(**inputs, forced_bos_token_id=tgt_token_id, max_length=384, use_cache=True)
            translated_parts.append(trans_tok.decode(outputs[0], skip_special_tokens=True))

        return " ".join(translated_parts)
    except Exception as e:
        print(f"Translation error: {e}")
        return text


@st.cache_resource(show_spinner=False)
def load_summarization_models(quantization_level="4-bit"):
    """Load summarization models with 4-bit quantization by default for speed"""
    models = {}
    if not TRANSFORMERS_AVAILABLE:
        return models

    kwargs = {"device_map": "auto"}
    if BNB_AVAILABLE:
        if quantization_level == "8-bit":
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        elif quantization_level == "4-bit":
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16
            )

    # 1. BART MODEL
    try:
        models['bart'] = {
            'tokenizer': AutoTokenizer.from_pretrained("sshleifer/distilbart-cnn-12-6"),
            'model': AutoModelForSeq2SeqLM.from_pretrained("sshleifer/distilbart-cnn-12-6", **kwargs)
        }
    except Exception as e:
        print(f"BART load failed: {e}")
        models['bart'] = None

    # 2. PEGASUS MODEL
    try:
        models['pegasus'] = {
            'tokenizer': AutoTokenizer.from_pretrained("google/pegasus-cnn_dailymail"),
            'model': AutoModelForSeq2SeqLM.from_pretrained("google/pegasus-cnn_dailymail", **kwargs)
        }
    except Exception as e:
        print(f"Pegasus load failed: {e}")
        models['pegasus'] = None

    # 3. FLAN-T5 MODEL
    try:
        t5_models_to_try = ["google/flan-t5-base", "google/flan-t5-small"]
        t5_loaded = False
        for t5_model in t5_models_to_try:
            try:
                models['flan-t5'] = {
                    'tokenizer': AutoTokenizer.from_pretrained(t5_model),
                    'model': AutoModelForSeq2SeqLM.from_pretrained(t5_model, **kwargs)
                }
                t5_loaded = True
                break
            except Exception:
                continue
        if not t5_loaded:
            models['flan-t5'] = None
    except Exception as e:
        print(f"FLAN-T5 load failed: {e}")
        models['flan-t5'] = None

    return models

@st.cache_resource(show_spinner=False)
def load_paraphrase_models(quantization_level="4-bit"):
    """Load paraphrase models with 4-bit quantization by default"""
    models = {}
    if not TRANSFORMERS_AVAILABLE:
        return models

    kwargs = {"device_map": "auto"}
    if BNB_AVAILABLE:
        if quantization_level == "8-bit":
            kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
        elif quantization_level == "4-bit":
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16
            )

    try:
        try:
            models['flan_t5'] = {
                'tokenizer': AutoTokenizer.from_pretrained("Vamsi/T5_Paraphrase_Paws"),
                'model': AutoModelForSeq2SeqLM.from_pretrained("Vamsi/T5_Paraphrase_Paws", **kwargs)
            }
        except Exception:
            try:
                models['flan_t5'] = {
                    'tokenizer': AutoTokenizer.from_pretrained("google/flan-t5-small"),
                    'model': AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small", **kwargs)
                }
            except Exception:
                models['flan_t5'] = None

        try:
            models['bart'] = {
                'tokenizer': AutoTokenizer.from_pretrained("eugenesiow/bart-paraphrase"),
                'model': AutoModelForSeq2SeqLM.from_pretrained("eugenesiow/bart-paraphrase", **kwargs)
            }
        except Exception:
            models['bart'] = None

        return models
    except Exception:
        return {}


def _detect_hallucination(original_text, generated_text):
    """Post-generation quality check to detect hallucinated output"""
    gen_words = generated_text.split()
    orig_words = set(original_text.lower().split())

    if len(gen_words) < 3:
        return True

    # Check for excessive repetition (same word appearing > 50% of output)
    from collections import Counter
    word_counts = Counter(w.lower().strip(".,!?();:'\"") for w in gen_words)
    most_common_count = word_counts.most_common(1)[0][1] if word_counts else 0
    if most_common_count > len(gen_words) * 0.5 and len(gen_words) > 20:
        return True

    # Check if output has too many words not in original (hallucination signal)
    # Only flag if >85% of words are completely novel AND output is long
    gen_clean = [w.lower().strip(".,!?();:'\"") for w in gen_words]
    novel_words = [w for w in gen_clean if w not in orig_words and len(w) > 3]
    if len(novel_words) > len(gen_words) * 0.85 and len(gen_words) > 30:
        return True

    return False


def simple_text_summarization(text, summary_length):
    """Simple extractive text summarization fallback"""
    try:
        sentences = sent_tokenize(text)
        if len(sentences) <= 2:
            return text[:100] + "..." if len(text) > 100 else text

        if summary_length == "Short":
            return " ".join(sentences[:max(1, len(sentences) // 4)])
        elif summary_length == "Medium":
            return " ".join(sentences[:max(2, len(sentences) // 2)])
        else:
            return " ".join(sentences[:max(3, int(len(sentences) * 0.75))])
    except:
        return text[:150] + "..." if len(text) > 150 else text


def local_summarize(text, summary_length, model_type, models_dict, target_lang="English"):
    """Summarization with anti-hallucination guardrails and multilanguage support"""
    model_key = model_type.lower()

    if (model_key not in models_dict or models_dict[model_key] is None):
        st.warning(f"⚠️ {model_type} model not available. Using fallback method.")
        result = simple_text_summarization(text, summary_length)
        if target_lang != "English":
            result = translate_text(result, "English", target_lang)
        return result

    model_info = models_dict[model_key]
    tokenizer = model_info['tokenizer']
    model = model_info['model']

    input_word_count = len(text.split())
    input_length = len(tokenizer.encode(text))

    # Adaptive length config with WIDER gaps between Short/Medium/Long
    is_long_doc = input_word_count >= 1000

    if is_long_doc:
        length_config = {
            "Short":  {"max_length": min(300, max(150, input_length // 4)),   "min_length": min(100, max(50, input_length // 6))},
            "Medium": {"max_length": min(700, max(400, int(input_length * 0.5))), "min_length": min(350, max(200, input_length // 3))},
            "Long":   {"max_length": min(1500, max(800, int(input_length * 0.85))), "min_length": min(700, max(500, int(input_length * 0.6)))}
        }
    else:
        safe_max = max(60, int(input_length * 0.95))
        length_config = {
            "Short":  {"max_length": min(60, max(20, input_length // 4)),   "min_length": min(10, max(5, input_length // 6))},
            "Medium": {"max_length": min(150, max(40, input_length // 2)),  "min_length": min(25, max(12, input_length // 4))},
            "Long":   {"max_length": min(safe_max, max(80, int(input_length * 0.9))), "min_length": min(50, max(25, input_length // 2))}
        }

    config = length_config.get(summary_length, length_config["Medium"])

    # Ensure min never exceeds max
    config["min_length"] = min(config["min_length"], config["max_length"] - 5)
    config["min_length"] = max(config["min_length"], 5)

    # FLAN-T5: length-specific prompts so Short/Medium/Long produce different results
    if model_key == 'flan-t5':
        if summary_length == "Short":
            prompt = f"Write a brief 2-3 sentence summary of the following text: {text}"
        elif summary_length == "Medium":
            prompt = f"Write a detailed summary of the following text, covering the main points: {text}"
        else:
            prompt = f"Write a comprehensive and thorough summary of the following text, covering all key points and important details: {text}"
    else:
        prompt = text

    try:
        with st.spinner(f"🧠 {model_type} generating summary..."):
            device = next(model.parameters()).device
            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
                padding=True
            ).to(device)

            gen_kwargs = {
                "max_new_tokens": config["max_length"],
                "min_new_tokens": config["min_length"],
                "num_beams": 2,
                "length_penalty": {"Short": 0.6, "Medium": 1.0, "Long": 1.8}.get(summary_length, 1.0),
                "no_repeat_ngram_size": 3,
                "early_stopping": True,
                "use_cache": True,
                "repetition_penalty": 1.5,
            }

            with torch.no_grad():
                outputs = model.generate(**inputs, **gen_kwargs)

            summary = tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Post-generation hallucination check
            if _detect_hallucination(text, summary):
                summary = simple_text_summarization(text, summary_length)

            if not summary.strip():
                summary = simple_text_summarization(text, summary_length)

            # For long documents, if summary is too short, pad with extractive sentences
            if is_long_doc and len(summary.split()) < 400:
                extractive_addition = simple_text_summarization(text, "Long")
                summary = summary + "\n\n" + extractive_addition

            # Translate if needed
            if target_lang != "English":
                with st.spinner(f"🌐 Translating to {target_lang}..."):
                    summary = translate_text(summary, "English", target_lang)

            return summary
    except Exception as e:
        st.error(f"❌ {model_type} AI MODEL ERROR: {str(e)}")
        result = simple_text_summarization(text, summary_length)
        if target_lang != "English":
            result = translate_text(result, "English", target_lang)
        return result


def apply_fallback_paraphrasing(text, complexity):
    words = text.split()
    if len(words) <= 3:
        return text

    substitutions = {
        "Beginner": {
            "utilize": "use", "facilitate": "help", "fundamental": "basic",
            "however": "but", "moreover": "also", "subsequently": "then",
            "very": "quite", "important": "key"
        },
        "Intermediate": {
            "use": "utilize", "help": "assist", "basic": "fundamental",
            "but": "however", "also": "furthermore", "then": "subsequently",
            "important": "significant", "good": "effective"
        },
        "Advanced": {
            "use": "leverage", "help": "facilitate", "basic": "foundational",
            "but": "nevertheless", "also": "moreover", "then": "thereafter",
            "show": "demonstrate", "important": "paramount", "good": "optimal"
        },
        "Expert": {
            "use": "employ", "help": "ameliorate", "basic": "rudimentary",
            "show": "elucidate", "make": "synthesize", "important": "critical", "good": "superior"
        }
    }
    sub_dict = substitutions.get(complexity, substitutions["Intermediate"])
    paraphrased_words = []
    for word in words:
        clean_word = word.strip(".,!?();:'\"").lower()
        if clean_word in sub_dict:
            new_word = sub_dict[clean_word]
            if word[0].isupper():
                new_word = new_word.capitalize()
            replaced = word.lower().replace(clean_word, new_word)
            if word[0].isupper():
                replaced = replaced.capitalize()
            paraphrased_words.append(replaced)
        else:
            paraphrased_words.append(word)
    return " ".join(paraphrased_words)


def paraphrase_with_model(text, complexity, style, model_type, models_dict, target_lang="English"):
    """Paraphrase text using specified model with multilanguage support"""
    model_key = model_type.lower().replace('-', '_')
    try:
        model_info = models_dict.get(model_key)
        if model_info is None:
            result = apply_fallback_paraphrasing(text, complexity)
            if target_lang != "English":
                result = translate_text(result, "English", target_lang)
            return result

        tokenizer = model_info['tokenizer']
        model = model_info['model']
        device = next(model.parameters()).device

        # Split text into smaller chunks for better paraphrasing quality
        sentences = sent_tokenize(text)
        chunks = []
        curr = []
        curr_len = 0
        for s in sentences:
            slen = len(s.split())
            if curr_len + slen > 80 and curr:
                chunks.append(" ".join(curr))
                curr = [s]
                curr_len = slen
            else:
                curr.append(s)
                curr_len += slen
        if curr:
            chunks.append(" ".join(curr))

        paraphrased_chunks = []
        for chunk in chunks:
            chunk_token_count = len(tokenizer.encode(chunk))

            if model_key == 'flan_t5':
                prompt = f"paraphrase the following text using different words and sentence structure: {chunk} </s>"
            else:
                prompt = f"paraphrase: {chunk}"

            inputs = tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding="max_length"
            ).to(device)

            # Scale output to match input length — fast greedy decoding
            max_out = max(150, int(chunk_token_count * 1.5))
            min_out = max(10, int(chunk_token_count * 0.6))

            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=max_out,
                    min_new_tokens=min_out,
                    num_beams=1,
                    no_repeat_ngram_size=3,
                    repetition_penalty=1.8,
                    use_cache=True
                )

            paraphrased = tokenizer.decode(outputs[0], skip_special_tokens=True)
            if len(paraphrased.strip()) > 10:
                paraphrased_chunks.append(paraphrased)
            else:
                paraphrased_chunks.append(chunk)

        final_paraphrase = " ".join(paraphrased_chunks)
        if not final_paraphrase.strip():
            final_paraphrase = apply_fallback_paraphrasing(text, complexity)

        # Translate if needed
        if target_lang != "English":
            with st.spinner(f"🌐 Translating to {target_lang}..."):
                final_paraphrase = translate_text(final_paraphrase, "English", target_lang)

        return final_paraphrase
    except Exception as e:
        st.error(f"❌ Paraphrasing Engine Error ({model_type}): {str(e)}")
        result = apply_fallback_paraphrasing(text, complexity)
        if target_lang != "English":
            result = translate_text(result, "English", target_lang)
        return result
