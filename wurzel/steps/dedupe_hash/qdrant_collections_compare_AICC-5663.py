import sys
import requests
import pandas as pd
from fuzzywuzzy import fuzz
import difflib
import openai
from tqdm import tqdm
import tlsh
import re

#QDRANT_URL = "https://qdrant.intra.oneai.yo-digital.com"
QDRANT_URL = 'https://qdrant.intra.dev.oneai.yo-digital.com/'
#API_KEY = "RSFR0bjRIQ1FUcT"
API_KEY = "T4qEDskPwkUGvfvb"
HEADERS = {
    "Content-Type": "application/json",
    "api-key": API_KEY
}
azure_endpoint = "https://gpt4-ch.openai.azure.com/"
api_key = "5f65edd5152a475dac99ea8f555dc3a9"
api_version = "2024-02-01"
deployment = "GPT4-CH"

client = openai.AzureOpenAI(
    api_key=api_key,
    api_version=api_version,
    azure_endpoint=azure_endpoint,
)

def get_collection_info(collection_name):
    response = requests.get(f"{QDRANT_URL}/collections/{collection_name}", headers=HEADERS)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error retrieving collection info for {collection_name}: {response.status_code}")
        print(response.text)
        return None

def calc_tlsh(text):
    if text and isinstance(text, str) and len(text) > 50:
        try:
            return tlsh.hash(text.encode('utf-8'))
        except Exception:
            return None
    return None

def get_all_points_as_df(collection_name):
    all_rows = []
    offset = None
    limit = 100

    collection_info = get_collection_info(collection_name)
    if collection_info is None:
        return pd.DataFrame()

    total_points = collection_info.get('result', {}).get('vectors_count')

    with tqdm(total=total_points, desc=f"Fetching {collection_name}", disable=total_points is None) as pbar:
        while True:
            payload = {
                "limit": limit,
                "with_payload": True,
                "with_vector": True
            }
            if offset:
                payload["offset"] = offset

            response = requests.post(
                f"{QDRANT_URL}/collections/{collection_name}/points/scroll",
                headers=HEADERS,
                json=payload
            )

            if response.status_code != 200:
                print(f"Error fetching points from {collection_name}: {response.status_code}")
                print(response.text)
                break

            data = response.json()
            points = data['result']['points']
            if not points:
                break

            for point in points:
                row = {
                    "id": point.get("id"),
                }
                if "payload" in point:
                    row.update(point["payload"])
                text = row.get("text")
                existing_tlsh = row.get("text_tlsh_hash")
                if existing_tlsh and isinstance(existing_tlsh, str) and len(existing_tlsh) > 0:
                    row["tlsh"] = existing_tlsh
                else:
                    row["tlsh"] = calc_tlsh(text)
                all_rows.append(row)

            offset = data['result'].get('next_page_offset')
            pbar.update(len(points))

            if offset is None:
                break

    return pd.DataFrame(all_rows)

def diff_snippet(a, b, context=20):
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

def identical_tlsh_analysis(df_a, df_b, tlsh_col):
    tlsh_a = set(df_a[tlsh_col].dropna())
    tlsh_b = set(df_b[tlsh_col].dropna())
    identical = tlsh_a & tlsh_b
    return identical, len(identical)

def fuzzy_tlsh_matches(df, tlsh_col, max_diff=10):
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

def suspicious_cases_analysis(df, matches, text_col):
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
                'diff_snippet': diff_snippet(text_a, text_b)
            })
    return suspicious

def analyze_extra_docs_detail(df_small, extra_docs, text_col='text', fuzzy_threshold=85):
    results = []
    small_texts = df_small[text_col].dropna().astype(str).tolist()
    for idx, row in extra_docs.iterrows():
        extra_text = str(row[text_col])
        best_ratio = 0
        best_match = ""
        best_match_idx = None
        for small_idx, small_text in enumerate(small_texts):
            ratio = fuzz.ratio(extra_text, small_text)
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = small_text
                best_match_idx = small_idx
        new_content = None
        if best_ratio < fuzzy_threshold:
            new_content = extra_text
        else:
            new_content = diff_snippet(extra_text, best_match)
        results.append({
            "index": idx,
            "point_index": idx + 1,
            "extra_text": extra_text,
            "best_ratio": best_ratio,
            "best_match_excerpt": best_match[:200],
            "best_match_idx": best_match_idx,
            "is_truly_new": best_ratio < fuzzy_threshold,
            "diff_to_best_match": new_content,
        })
    return results

def gpt_contradict_check(doc1, doc2, idx1=None, idx2=None):
    doc1_header = f"[Index {idx1} (Point {idx1+1})]" if idx1 is not None else ""
    doc2_header = f"[Index {idx2} (Point {idx2+1})]" if idx2 is not None else ""
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
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {'role': 'system', 'content': 'You are a critical and precise analyst for technical documents. Only use the word "contradiction" if you can literally quote two sentences from the documents that directly contradict each other. Otherwise, do not use this word.'},
                {'role': 'user', 'content': prompt},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"

def extract_gpt_shortform(gpt_text):
    """
    Extracts the final recommendation from the GPT answer.
    Only returns the content inside the last pair of square brackets at the end of the answer.
    """
    if not isinstance(gpt_text, str):
        return ""
    match = re.search(r"\[([^\[\]]+)\]\s*$", gpt_text.strip())
    if match:
        return match.group(1).strip()
    return ""

def compare_tlsh_sha256(df1, df2):
    # Set für schnellen Vergleich
    sha256_set_2 = set(df2['text_sha256_hash'].dropna())
    tlsh_set_2 = set(df2['tlsh'].dropna())
    sha256_set_1 = set(df1['text_sha256_hash'].dropna())
    tlsh_set_1 = set(df1['tlsh'].dropna())

    results = []

    # Prüfe für jedes Dokument in df1
    for idx, row in df1.iterrows():
        sha256 = row.get('text_sha256_hash')
        tlsh_val = row.get('tlsh')
        doc_id = row.get('id', idx)
        sha256_match = sha256 in sha256_set_2 if pd.notna(sha256) else False
        tlsh_match = tlsh_val in tlsh_set_2 if pd.notna(tlsh_val) else False
        results.append({
            'id': doc_id,
            'sha256': sha256,
            'tlsh': tlsh_val,
            'sha256_match_in_other': sha256_match,
            'tlsh_match_in_other': tlsh_match,
            'agreement': sha256_match == tlsh_match
        })

    # Prüfe für jedes Dokument in df2 (optional, falls beide Richtungen gewünscht)
    for idx, row in df2.iterrows():
        sha256 = row.get('text_sha256_hash')
        tlsh_val = row.get('tlsh')
        doc_id = row.get('id', idx)
        sha256_match = sha256 in sha256_set_1 if pd.notna(sha256) else False
        tlsh_match = tlsh_val in tlsh_set_1 if pd.notna(tlsh_val) else False
        results.append({
            'id': doc_id,
            'sha256': sha256,
            'tlsh': tlsh_val,
            'sha256_match_in_other': sha256_match,
            'tlsh_match_in_other': tlsh_match,
            'agreement': sha256_match == tlsh_match
        })

    results_df = pd.DataFrame(results)
    print("\nVergleich TLSH vs. SHA256:")
    print(f"- Anzahl Dokumente mit Übereinstimmung (SHA256): {results_df['sha256_match_in_other'].sum()}")
    print(f"- Anzahl Dokumente mit Übereinstimmung (TLSH): {results_df['tlsh_match_in_other'].sum()}")
    print(f"- Anzahl Dokumente, bei denen beide Methoden gleich entscheiden: {results_df['agreement'].sum()} von {len(results_df)}")
    print(f"- Davon identisch (beide True): {(results_df['sha256_match_in_other'] & results_df['tlsh_match_in_other']).sum()}")
    print(f"- Davon unterschiedlich (SHA256≠TLSH): {(results_df['sha256_match_in_other'] != results_df['tlsh_match_in_other']).sum()}")
    print("\nBeispiele für unterschiedliche Ergebnisse:")
    print(results_df[results_df['agreement'] == False].head(10)[['id', 'sha256_match_in_other', 'tlsh_match_in_other']])

    return results_df

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python qdrant_compare.py <collection_1_name> <collection_2_name>")
        sys.exit(1)

    collection_1 = sys.argv[1]
    collection_2 = sys.argv[2]

    # Load data
    df1 = get_all_points_as_df(collection_1)
    df2 = get_all_points_as_df(collection_2)

    # === NEU: TLSH & SHA256 Vergleich ===
    compare_tlsh_sha256(df1, df2)

    # Determine smaller and larger collection
    if len(df1) <= len(df2):
        df_small, df_large = df1, df2
        name_small, name_large = collection_1, collection_2
    else:
        df_small, df_large = df2, df1
        name_small, name_large = collection_2, collection_1

    print(f"\nSmaller collection: {name_small} ({len(df_small)} documents)")
    print(f"Larger collection: {name_large} ({len(df_large)} documents)")

    # 1. Exactly identical documents
    identical_set, identical_count = identical_tlsh_analysis(df_small, df_large, 'tlsh')

    # 2. Extra documents in the larger collection
    tlsh_small = set(df_small['tlsh'].dropna())
    tlsh_large = set(df_large['tlsh'].dropna())
    extra_tlsh = tlsh_large - tlsh_small
    extra_docs = df_large[df_large['tlsh'].isin(extra_tlsh)]

    # 2b. Detailed analysis of extra documents
    extra_analysis = analyze_extra_docs_detail(df_small, extra_docs, text_col='text', fuzzy_threshold=85)
    extra_analysis_df = pd.DataFrame(extra_analysis)

    # 3. Redundancies and contradictions within the large collection
    fuzzy_matches = fuzzy_tlsh_matches(df_large, 'tlsh', max_diff=10)
    suspicious = suspicious_cases_analysis(df_large, fuzzy_matches, 'text')
    suspicious_df = pd.DataFrame(suspicious)

    # GPT analysis for redundant/contradictory pairs
    if not suspicious_df.empty:
        print(f"\nStarting GPT analysis for {len(suspicious_df)} redundant/contradictory pairs...")
        gpt_results = []
        gpt_shortforms = []
        for i, row in tqdm(suspicious_df.iterrows(), total=len(suspicious_df)):
            gpt_result = gpt_contradict_check(
                row['text_a'], row['text_b'],
                row['index_a'], row['index_b']
            )
            gpt_results.append(gpt_result)
            gpt_shortforms.append(extract_gpt_shortform(gpt_result))
        suspicious_df['gpt_recommendation'] = gpt_results
        suspicious_df['gpt_shortform'] = gpt_shortforms

    # Identical documents as DataFrame
    identical_docs_df = df_large[df_large['tlsh'].isin(identical_set)].copy()
    identical_docs_df["point_index"] = identical_docs_df.index + 1

    # Extra documents as DataFrame (with index)
    extra_docs_with_idx = extra_docs.copy()
    extra_docs_with_idx["point_index"] = extra_docs_with_idx.index + 1

    # Save to Excel
    excel_name = f"compare_{name_small}_vs_{name_large}.xlsx"
    with pd.ExcelWriter(excel_name, engine="openpyxl") as writer:
        identical_docs_df.to_excel(writer, sheet_name="Identical_Documents", index=False)
        extra_docs_with_idx.to_excel(writer, sheet_name="Extra_Documents", index=False)
        extra_analysis_df.to_excel(writer, sheet_name="Extra_Details", index=False)
        suspicious_df.to_excel(writer, sheet_name="Redundant_or_Contradictory_Pairs", index=False)

    print(f"\nAll results have been saved to {excel_name}.")

    print("\n" + "="*80)
    print("🔍 Comparison completed")
    print("="*80)

    print(f"📦 Comparison between collections '{collection_1}' and '{collection_2}'")
    print(f"- Smaller collection '{name_small}' contains {len(df_small)} documents.")
    print(f"- Larger collection '{name_large}' contains {len(df_large)} documents.\n")

    print("✅ Summary of results:")
    print(f"1️⃣ Exactly identical documents (TLSH match): {identical_count}")
    print(f"2️⃣ Additional documents in larger collection: {len(extra_docs)}")
    print(f"   → Of these, truly new or significantly different content (<85% similarity): {sum([r['is_truly_new'] for r in extra_analysis])}")
    print(f"3️⃣ Potentially redundant or contradictory pairs in large collection (TLSH-similar): {len(fuzzy_matches)}")
    print(f"   → Remaining suspicious cases after fuzzy check: {len(suspicious)}")
    if not suspicious_df.empty:
        print("   → GPT recommendations:")
        print(
            f"      - 'Keep both(desp.redundancy)' : {sum((s == 'both') or ('Redundancy' in str(s)) or (str(s).strip() == '') or pd.isna(s) for s in suspicious_df['gpt_shortform'])}")
        print(f"      - 'Keep only document 1'     : {sum(s == 'b remove' for s in suspicious_df['gpt_shortform'])}")
        print(f"      - 'Keep only document 2'     : {sum(s == 'a remove' for s in suspicious_df['gpt_shortform'])}")
        print(f"      - 'Contradiction, clarification needed': {sum(s == 'contradiction' for s in suspicious_df['gpt_shortform'])}")
    else:
        print("   → No GPT assessment performed (no suspicious cases found).")
