import itertools
import pandas as pd
import requests
from tqdm import tqdm
from logging import getLogger
import tlsh
from fuzzywuzzy import fuzz
import difflib
import openai
import re
from wurzel.step import TypedStep
from wurzel.exceptions import StepFailed
from wurzel.step.settings import Settings
from qdrant_client import QdrantClient, models

log = getLogger(__name__)



#from wurzel.settings import QdrantCompareSettings

from settings import QdrantCompareSettings



class QdrantCompareStep(TypedStep[QdrantCompareSettings, None, dict]):
    """Vergleicht zwei Qdrant-Collections und analysiert Unterschiede, Redundanzen und Widersprüche."""

    #client: QdrantClient

    def __init__(self):
        super().__init__()
        self.headers = {
            "Content-Type": "application/json",
            "api-key": self.settings.API_KEY
        }
        self.gpt_client = openai.AzureOpenAI(
            api_key="5f65edd5152a475dac99ea8f555dc3a9",
            api_version="2024-02-01",
            azure_endpoint="https://gpt4-ch.openai.azure.com/",
        )

    def run(self, inpt=None):
        # 1. Daten laden

        last_2_collections = self.list_top_collections(self.settings.QDRANT_URL, headers=self.headers, prefix= self.settings.prefix, top_n=2, verbose=True)
        print(last_2_collections)
        df1 = self._get_all_points_as_df(last_2_collections[0])  # Verwende die erste Collection aus der Liste
        df2 = self._get_all_points_as_df(last_2_collections[1])  # Verwende die zweite Collection aus der Liste
        n1 = len(df1)
        n2 = len(df2)
        print(n1, n2)

        # 2. Bestimmen, welche Collection kleiner ist
        if len(df1) <= len(df2):
            df_small, df_large = df1, df2
            name_small, name_large = last_2_collections[0], last_2_collections[1]
        else:
            df_small, df_large = df2, df1
            name_small, name_large = last_2_collections[1], last_2_collections[0]

        log.info(f"Smaller collection: {name_small} ({len(df_small)})")
        log.info(f"Larger collection: {name_large} ({len(df_large)})")

        # 3. Identische Dokumente

        identical_set, identical_count = self._identical_tlsh_analysis(df_small, df_large, 'tlsh')

        # 4. Extra-Dokumente
        tlsh_small = set(df_small['tlsh'].dropna())
        tlsh_large = set(df_large['tlsh'].dropna())
        extra_tlsh = tlsh_large - tlsh_small
        extra_docs = df_large[df_large['tlsh'].isin(extra_tlsh)]

        # 5. Detailanalyse der Extra-Dokumente
        extra_analysis = self._analyze_extra_docs_detail(df_small, extra_docs, text_col='text', threshold=self.settings.FUZZY_THRESHOLD)
        extra_analysis_df = pd.DataFrame(extra_analysis)

        # 6. Redundanzen und Widersprüche in der großen Collection
        fuzzy_matches = self._fuzzy_tlsh_matches(df_large, 'tlsh', self.settings.TLSH_MAX_DIFF)
        suspicious = self._suspicious_cases_analysis(df_large, fuzzy_matches, 'text')
        suspicious_df = pd.DataFrame(suspicious)

        # 7. GPT-Analyse für verdächtige Paare
        gpt_results, gpt_shortforms = [], []
        if not suspicious_df.empty:
            log.info(f"Starting GPT analysis for {len(suspicious_df)} pairs...")
            for i, row in tqdm(suspicious_df.iterrows(), total=len(suspicious_df)):
                gpt_result = self._gpt_contradict_check(row['text_a'], row['text_b'], row['index_a'], row['index_b'])
                gpt_results.append(gpt_result)
                gpt_shortforms.append(self._extract_gpt_shortform(gpt_result))
            suspicious_df['gpt_recommendation'] = gpt_results
            suspicious_df['gpt_shortform'] = gpt_shortforms

        # 8. Ergebnisse als DataFrames
        identical_docs_df = df_large[df_large['tlsh'].isin(identical_set)].copy()
        identical_docs_df["point_index"] = identical_docs_df.index + 1
        extra_docs_with_idx = extra_docs.copy()
        extra_docs_with_idx["point_index"] = extra_docs_with_idx.index + 1

        # 9. Export als Excel
        #excel_name = f"compare_{name_small}_vs_{name_large}.xlsx"
        """with pd.ExcelWriter(excel_name, engine="openpyxl") as writer:
            identical_docs_df.to_excel(writer, sheet_name="Identical_Documents", index=False)
            extra_docs_with_idx.to_excel(writer, sheet_name="Extra_Documents", index=False)
            extra_analysis_df.to_excel(writer, sheet_name="Extra_Details", index=False)
            suspicious_df.to_excel(writer, sheet_name="Redundant_or_Contradictory_Pairs", index=False)

        log.info(f"All results have been saved to {excel_name}.")"""

        # 10. Zusammenfassung (als Log-Ausgabe)
        log.info(f"Comparison between '{name_small}' and '{name_large}'")
        log.info(f"Identical: {identical_count}, Extra: {len(extra_docs)}, Suspicious: {len(suspicious)}")
        if not suspicious_df.empty:
            log.info("GPT recommendations summary:")
            log.info(f"Keep both (Redundancy): {sum((s == 'both') or ('Redundancy' in str(s)) or (str(s).strip() == '') or pd.isna(s) for s in suspicious_df['gpt_shortform'])}")
            log.info(f"Keep only document 1: {sum(s == 'b remove' for s in suspicious_df['gpt_shortform'])}")
            log.info(f"Keep only document 2: {sum(s == 'a remove' for s in suspicious_df['gpt_shortform'])}")
            log.info(f"Contradiction, clarification needed: {sum(s == 'contradiction' for s in suspicious_df['gpt_shortform'])}")

        # Rückgabe der wichtigsten Ergebnisse als Dict
        return {
            "comparison between": [last_2_collections[0],n1, last_2_collections[1],n2],
            "tslh_identical_documents": identical_count,
            "tslh_differing_docs": len(extra_docs),
            "duplicates_with_contradictions": len(suspicious),



        }

    def list_top_collections(self, qdrant_url, headers=None, prefix="germany_v", top_n=2, verbose=True):
        """
        Gibt die Namen der `top_n`-Collections mit dem höchsten numerischen Suffix für ein gegebenes Präfix zurück.

        Args:
            qdrant_url (str): Qdrant-Basis-URL.
            headers (dict, optional): HTTP-Header mit optionalem API-Key.
            prefix (str): Das Präfix der Collections, z. B. "germany_v".
            top_n (int): Wie viele Collections mit höchster Nummer zurückgegeben werden sollen.
            verbose (bool): Ob Ergebnisse gedruckt werden sollen.

        Returns:
            list: Liste der `top_n`-Collection-Namen mit höchstem Index, oder leere Liste bei Fehler.
        """
        url = f"{qdrant_url}/collections"
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Fehler beim Abrufen der Collections: {e}")
            return []

        collections = response.json().get("result", {}).get("collections", [])
        collection_names = [col.get("name") for col in collections]

        # Filtere nach passendem Präfix und extrahiere numerische Suffixe
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        matching = []
        for name in collection_names:
            match = pattern.match(name)
            if match:
                number = int(match.group(1))
                matching.append((number, name))

        # Sortiere absteigend nach Nummer und nimm die Top-N
        matching.sort(reverse=True)
        top_collections = [name for _, name in matching[:top_n]]

        if verbose:
            if top_collections:
                print(f"Top {top_n} Collections with prefix '{prefix}':")
                for name in top_collections:
                    print(f" - {name}")
            else:
                print(f"Keine Collections mit Präfix '{prefix}' gefunden.")

        return top_collections



    def _get_collection_info(self, collection_name):
        response = requests.get(
            f"{self.settings.QDRANT_URL}/collections/{collection_name}",
            headers=self.headers
        )

        return response.json() if response.status_code == 200 else None

    def _calc_tlsh(self, text):
        if text and isinstance(text, str) and len(text) > 50:
            try:
                return tlsh.hash(text.encode('utf-8'))
            except Exception:
                return None
        return None

    def _get_all_points_as_df(self, collection_name):
        all_rows = []
        offset = None
        limit = 100

        collection_info = self._get_collection_info(collection_name)

        total_points = collection_info.get('result', {}).get('vectors_count') if collection_info else 0

        with tqdm(total=total_points, desc=f"Fetching {collection_name}") as pbar:
            while True:
                payload = {"limit": limit, "with_payload": True, "with_vector": True}
                if offset:
                    payload["offset"] = offset

                response = requests.post(
                    f"{self.settings.QDRANT_URL}/collections/{collection_name}/points/scroll",
                    headers=self.headers,
                    json=payload
                )

                if not response.ok:
                    break

                data = response.json()
                points = data['result']['points']
                if not points:
                    break

                for point in points:
                    row = point.get("payload", {})
                    row["id"] = point["id"]
                    row["tlsh"] = row.get("text_tlsh_hash") or self._calc_tlsh(row.get("text"))
                    all_rows.append(row)

                offset = data['result'].get('next_page_offset')
                pbar.update(len(points))
                if not offset:
                    break

        return pd.DataFrame(all_rows)

    def _identical_tlsh_analysis(self, df_a, df_b, tlsh_col):
        tlsh_a = set(df_a[tlsh_col].dropna())
        tlsh_b = set(df_b[tlsh_col].dropna())
        return tlsh_a & tlsh_b, len(tlsh_a & tlsh_b)

    def _fuzzy_tlsh_matches(self, df, tlsh_col, max_diff):
        matches = []
        hashes = df[tlsh_col].dropna()
        idx_hash = list(hashes.items())
        for i in range(len(idx_hash)):
            idx_a, hash_a = idx_hash[i]
            for j in range(i+1, len(idx_hash)):
                idx_b, hash_b = idx_hash[j]
                try:
                    diff = tlsh.diff(hash_a, hash_b)
                    if diff is not None and diff <= max_diff:
                        matches.append((idx_a, idx_b, diff))
                except Exception:
                    continue
        return matches

    def _diff_snippet(self, a, b, context=20):
        sm = difflib.SequenceMatcher(None, a, b)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                start_a = max(i1 - context, 0)
                end_a = min(i2 + context, len(a))
                start_b = max(j1 - context, 0)
                end_b = min(j2 + context, len(b))
                snippet_a = a[start_a:end_a]
                snippet_b = b[start_b:end_b]
                return f"a:[{snippet_a}] | b:[{snippet_b}]"
        return ""

    def _suspicious_cases_analysis(self, df, matches, text_col):
        suspicious = []
        for idx_a, idx_b, diff in matches:
            text_a = str(df.loc[idx_a, text_col])
            text_b = str(df.loc[idx_b, text_col])
            fuzzval = fuzz.ratio(text_a, text_b)
            if fuzzval < 100:
                suspicious.append({
                    'index_a': idx_a,
                    'point_index_a': idx_a+1,
                    'index_b': idx_b,
                    'point_index_b': idx_b+1,
                    'text_a': text_a,
                    'text_b': text_b,
                    'fuzz_ratio': fuzzval,
                    'tlsh_diff': diff,
                    'diff': self._diff_snippet(text_a, text_b)
                })
        return suspicious

    def _analyze_extra_docs_detail(self, df_base, df_extra, text_col, threshold):
        results = []
        for idx, extra_row in df_extra.iterrows():
            extra_text = str(extra_row[text_col])
            best_ratio = 0
            for base_text in df_base[text_col]:
                ratio = fuzz.ratio(extra_text, str(base_text))
                if ratio > best_ratio:
                    best_ratio = ratio
            is_truly_new = best_ratio < threshold
            results.append({
                "index": idx,
                "point_index": idx + 1,
                "best_ratio": best_ratio,
                "is_truly_new": is_truly_new,
                "diff": self._diff_snippet(extra_text, str(df_base[text_col].iloc[0]))
            })
        return results

    """def _gpt_contradict_check(self, doc1, doc2, idx1=None, idx2=None):
        response = self.gpt_client.chat.completions.create(
            model=self.settings.GPT_MODEL,
            messages=[{
                "role": "user",
                "content": f"Analyze these documents for contradictions:\n\nDOC1:{doc1}\n\nDOC2:{doc2}"
            }]
        )
        return {
            "index_a": idx1,
            "index_b": idx2,
            "gpt_analysis": response.choices[0].message.content,
            "contradiction_found": "contradiction" in response.choices[0].message.content.lower()
        }
    """
    def _gpt_contradict_check(self, doc1, doc2, idx1=None, idx2=None):
        doc1_header = f"[Index {idx1} (Point {idx1 + 1})]" if idx1 is not None else ""
        doc2_header = f"[Index {idx2} (Point {idx2 + 1})]" if idx2 is not None else ""

        prompt = f"""
    You are an expert technical editor. You receive two FAQ documents and must analyze their relationship.

    **IMPORTANT INSTRUCTIONS:**
    - ONLY use the word 'contradiction' if you have found a clear, factual, and direct contradiction between the two documents. 
    - DO NOT use the word 'contradiction' for minor differences, missing information, differences in detail, or differences in wording.
    - If there is NO contradiction, DO NOT use the word 'contradiction' ANYWHERE in your answer.
    - If you are unsure, DO NOT use the word 'contradiction'.
    - If the documents are simply different or complementary, but not contradictory, DO NOT use the word 'contradiction'.
    - If you use the word 'contradiction', you MUST quote the exact sentences or phrases from both documents that contradict each other, and explain why they are contradictory.
    - If there is no contradiction, check if the documents are redundant. Only use 'redundancy' or 'redundant' if the information is truly duplicated and the two documents share the same exact semantic information.

    **YOUR TASKS:**
    1. Decide if the two documents are in factual contradiction. If yes, quote the exact contradictory statements and explain the contradiction.
    2. If there is NO contradiction, check if the documents are redundant (i.e., only if they contain the exact semantic same information). If so, state which document is redundant and what is duplicated.
    3. If neither contradiction nor redundancy is present, state that both documents are needed.

    **FINAL RECOMMENDATION:**  
    Write ONLY ONE of the following at the end of your answer (and nothing else):
    - ['Contradiction']   (ONLY if you have quoted and explained a real contradiction)
    - ['Redundancy']      (ONLY if you have explained real redundancy)
    - ['Keep both']       (if both are needed)
    - ['Keep only document 1']
    - ['Keep only document 2']

    Here are the two documents:
    Document 1 {doc1_header}:
    \"\"\"{doc1}\"\"\"

    Document 2 {doc2_header}:
    \"\"\"{doc2}\"\"\"
    """

        try:
            response = self.gpt_client.chat.completions.create(
                model=self.settings.GPT_MODEL,
                messages=[
                    {'role': 'system',
                     'content': 'You are a critical and precise analyst for technical documents. Only use the word "contradiction" if you can literally quote two sentences from the documents that directly contradict each other. Otherwise, do not use this word.'},
                    {'role': 'user', 'content': prompt},
                ],
            )
            result_text = response.choices[0].message.content.strip()
            return {
                "index_a": idx1,
                "index_b": idx2,
                "gpt_analysis": result_text,
                "contradiction_found": "contradiction" in result_text.lower()
            }
        except Exception as e:
            return {
                "index_a": idx1,
                "index_b": idx2,
                "gpt_analysis": f"Error: {e}",
                "contradiction_found": False
            }

    def _extract_gpt_shortform(self, gpt_result):
        # Dummy-Implementierung, passe nach Bedarf an!
        content = gpt_result.get("gpt_analysis", "").lower()
        if not isinstance(content, str):
            return ""
        if "contradiction" in content:
            return "contradiction"
        if "keep both" in content or "redundancy" in content:
            return "both"
        if "remove document 1" in content:
            return "a remove"
        if "remove document 2" in content:
            return "b remove"
        return ""





if __name__ == "__main__":
    # Setze deine Parameter
    settings = QdrantCompareSettings()
    """ settings.QDRANT_URL = "https://qdrant.intra.oneai.yo-digital.com"
        settings.API_KEY = "RSFR0bjRIQ1FUcT"
        settings.OPAI_API_KEY = "5f65edd5152a475dac99ea8f555dc3a9"
    """
    step = QdrantCompareStep()
    step.settings = settings

    # Step ausführen
    result = step.run()
    print("Vergleich abgeschlossen. Zusammenfassung:")
    print(result)


