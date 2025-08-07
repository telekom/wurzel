# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG (opensource@telekom.de)
#
# SPDX-License-Identifier: Apache-2.0

# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG

# pylint: disable=c-extension-no-member

# Standard library imports
import atexit
import difflib
import json
import logging
import os
import re
import socket
from datetime import datetime

import httpx
import openai
import pandas as pd
import requests
import tlsh
from fuzzywuzzy import fuzz
from tqdm import tqdm

from wurzel.step import TypedStep
from wurzel.steps.dedupe_hash.settings import QdrantCompareSettings
from wurzel.steps.qdrant.step import QdrantConnectorStep


class JsonArrayLogHandler(logging.Handler):
    """Arranges all logs to one JSON file."""

    def __init__(self, filepath):
        super().__init__()
        self.filepath = filepath
        self.messages = []
        self.timestamp = None
        atexit.register(self._flush_logs)

    def emit(self, record):
        if self.timestamp is None:
            self.timestamp = self.formatter.formatTime(record)
        self.messages.append(record.getMessage())

    def _flush_logs(self):
        if self.timestamp is None:
            return
        log_output = {"timestamp": self.timestamp, "messages": self.messages}
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(log_output, f, indent=2)


# Setup Logger
LOG_DIR = "/Users/A1167082/Desktop/qdrant_compare_logs"
os.makedirs(LOG_DIR, exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
log_path = os.path.join(LOG_DIR, f"compare_log_{timestamp}.json")

log = logging.getLogger("simple_json_logger")
log.setLevel(logging.INFO)

handler = JsonArrayLogHandler(log_path)
handler.setFormatter(logging.Formatter(fmt="%(asctime)s", datefmt="%Y-%m-%d %H:%M:%S"))
log.addHandler(handler)


class QdrantCompareStep(TypedStep[QdrantCompareSettings, QdrantConnectorStep, dict]):
    """Compares the two most recent Qdrant collections to identify identical entries,
    newly added documents, redundant content, and potential contradictions.

    Main functionality:
    - Automatically fetches the two latest Qdrant collections matching a given prefix.
    - Uses TLSH (Trend Micro Locality Sensitive Hashing) to detect identical or similar documents.
    - Detects extra documents in the larger collection that are not in the smaller one.
    - Uses fuzzy string matching to detect near-duplicates.
    - Applies GPT-based analysis to semantically assess potential contradictions or redundancies.
    - Logs key statistics and returns a summary dictionary of the comparison.

    Workflow steps:
    1. Load the two latest Qdrant collections using the provided prefix.
    2. Identify identical documents using TLSH hashes.
    3. Check percentage of identical documents and warn, if it falls below a certain threshold
    4. Analyze extra documents in the larger collection.
    5. Detect suspiciously similar documents using fuzzy matching.
    6. Use GPT to semantically evaluate whether pairs are redundant, contradictory, or unclear.
    7. Output a summary of results via logging and return values.

    Returns:
        dict: A dictionary containing:
            - Collection names and sizes
            - Number of identical documents
            - Number of extra (new) documents
            - Number of suspicious duplicates with potential contradictions

    Requirements:
    - A working Qdrant API connection with a valid API key.
    - TLSH hashes and a 'text' field must be present in the Qdrant vectors.
    - A functional Azure OpenAI GPT client must be configured.

    """

    def __init__(self):
        super().__init__()
        self.headers = {"Content-Type": "application/json", "api-key": self.settings.QDRANT_API_KEY}
        self.gpt_client = openai.AzureOpenAI(
            api_key=self.settings.OPAI_API_KEY, api_version="2024-02-01", azure_endpoint=self.settings.AZURE_ENDPOINT
        )

    def run(self, inpt=QdrantConnectorStep):
        """Main execution method - refactored into smaller functions."""
        collections = self._load_and_validate_collections()
        df_small, df_large, name_small, name_large = self._prepare_dataframes(collections)

        # Perform analysis
        identical_set, identical_count = self._identical_tlsh_analysis(df_small, df_large, "tlsh")
        log.info(identical_set)
        extra_docs = self._find_extra_documents(df_small, df_large)

        suspicious_df = self._find_suspicious_matches(df_large)

        # Generate results and summary
        return self._generate_comparison_summary(
            collections, identical_count, extra_docs, suspicious_df, name_small, name_large, len(df_small), len(df_large)
        )

    def _load_and_validate_collections(self):
        """Load collections and validate sequence."""
        last_2_collections = self.list_top_collections(
            self.settings.QDRANT_URL, headers=self.headers, prefix=self.settings.QDRANT_COLLECTION_PREFIX, top_n=2
        )
        log.info(last_2_collections)

        self._validate_collection_sequence(last_2_collections)
        return last_2_collections

    def _validate_collection_sequence(self, collections):
        """Validate that collections follow expected numbering sequence."""
        if len(collections) == 2:
            pattern = re.compile(rf"^{re.escape(self.settings.QDRANT_COLLECTION_PREFIX)}(\d+)$")
            match_latest = pattern.match(collections[0])
            match_prev = pattern.match(collections[1])

            if match_latest and match_prev:
                latest_num = int(match_latest.group(1))
                prev_num = int(match_prev.group(1))
                if latest_num - prev_num != 1:
                    log.info(f"Predecessor collection with number {latest_num - 1} does not exist. Found collections: {collections}")
            else:
                log.info("Collection names do not match the expected pattern.")
        else:
            log.info(f"Less than 2 collections found: {collections}")

    def _prepare_dataframes(self, collections):
        """Load dataframes and determine which is smaller/larger."""
        df1 = self._get_all_points_as_df(collections[0])
        df2 = self._get_all_points_as_df(collections[1])

        # Determine which collection is smaller
        if len(df1) <= len(df2):
            df_small, df_large = df1, df2
            name_small, name_large = collections[0], collections[1]
        else:
            df_small, df_large = df2, df1
            name_small, name_large = collections[1], collections[0]

        log.info(f"Smaller collection: {name_small} ({len(df_small)})")
        log.info(f"Larger collection: {name_large} ({len(df_large)})")

        return df_small, df_large, name_small, name_large

    def _identical_tlsh_analysis(self, df_a, df_b, tlsh_col):
        """Find identical documents based on TLSH hashes and return set and count."""
        tlsh_a = set(df_a[tlsh_col].dropna())
        tlsh_b = set(df_b[tlsh_col].dropna())
        intersection = tlsh_a & tlsh_b
        return intersection, len(intersection)

    def _find_extra_documents(self, df_small, df_large):
        """Find documents that exist in large collection but not in small one."""
        tlsh_small = set(df_small["tlsh"].dropna())
        tlsh_large = set(df_large["tlsh"].dropna())
        extra_tlsh = tlsh_large - tlsh_small
        return df_large[df_large["tlsh"].isin(extra_tlsh)]

    def _find_suspicious_matches(self, df_large):
        """Find and analyze suspicious matches using GPT."""
        fuzzy_matches = self._fuzzy_tlsh_matches(df_large, "tlsh", self.settings.TLSH_MAX_DIFF)
        suspicious = self._suspicious_cases_analysis(df_large, fuzzy_matches, "text")
        suspicious_df = pd.DataFrame(suspicious)

        # GPT analysis for suspicious pairs
        if not suspicious_df.empty:
            log.info(f"Starting GPT analysis for {len(suspicious_df)} pairs...")
            gpt_results, gpt_shortforms = self._analyze_suspicious_pairs_with_gpt(suspicious_df)
            suspicious_df["gpt_recommendation"] = gpt_results
            suspicious_df["gpt_shortform"] = gpt_shortforms

        return suspicious_df

    def _analyze_suspicious_pairs_with_gpt(self, suspicious_df):
        """Analyze suspicious pairs using GPT."""
        gpt_results, gpt_shortforms = [], []

        for _, row in tqdm(suspicious_df.iterrows(), total=len(suspicious_df)):
            gpt_result = self._gpt_contradict_check(row["text_a"], row["text_b"], row["index_a"], row["index_b"])
            gpt_results.append(gpt_result)
            gpt_shortforms.append(self._extract_gpt_shortform(gpt_result))

        return gpt_results, gpt_shortforms

    def _generate_comparison_summary(self, collections, identical_count, extra_docs, suspicious_df, name_small, name_large, n1, n2):
        """Generate final comparison summary and logs."""
        # Create result DataFrames
        self._create_result_dataframes(extra_docs)

        # Log summary
        self._log_comparison_summary(name_small, name_large, identical_count, extra_docs, suspicious_df, n1, n2)

        # Return results dictionary
        return {
            "comparison between": [collections[0], n1, collections[1], n2],
            "tslh_identical_documents": identical_count,
            "tslh_differing_docs": len(extra_docs),
            "duplicates_with_contradictions": len(suspicious_df),
        }

    def _create_result_dataframes(self, extra_docs):
        """Create result DataFrames with point indices."""
        extra_docs_with_idx = extra_docs.copy()
        extra_docs_with_idx["point_index"] = extra_docs_with_idx.index + 1

    def _log_comparison_summary(self, name_small, name_large, identical_count, extra_docs, suspicious_df, n1, n2):
        """Log the comparison summary."""
        log.info(f"Comparison between '{name_small}' and '{name_large}'")
        log.info(f"Identical: {identical_count}, Extra: {len(extra_docs)}, Suspicious: {len(suspicious_df)}")

        # Warning if percentage of identical documents falls below allowed threshold
        total_compared = min(n1, n2)
        log.info(f"Total comparison: {total_compared}")

        if total_compared > 0:
            identical_ratio = identical_count / total_compared
            if identical_ratio < self.settings.IDENTICAL_WARNING_THRESHOLD:
                log.info(
                    f"Identical document count: {identical_count}"
                    f"⚠️ Only {identical_ratio:.2%} identical documents between "
                    f"'{name_small}' and '{name_large}' "
                    f"(Threshold: {self.settings.IDENTICAL_WARNING_THRESHOLD:.0%})"
                )

        if not suspicious_df.empty:
            self._log_gpt_recommendations_summary(suspicious_df)

    def _log_gpt_recommendations_summary(self, suspicious_df):
        """Log GPT recommendations summary."""
        log.info("GPT recommendations summary:")

        shortforms = suspicious_df["gpt_shortform"]
        keep_both_count = sum((s == "both") or ("redundancy" in str(s).lower()) or (str(s).strip() == "") or pd.isna(s) for s in shortforms)

        log.info("Keep both (Redundancy): %s", keep_both_count)
        log.info(f"Keep only document 1: {sum(s == 'a remove' for s in shortforms)}")
        log.info(f"Keep only document 2: {sum(s == 'b remove' for s in shortforms)}")
        log.info(f"Contradiction, clarification needed: {sum(s == 'contradiction' for s in shortforms)}")

    def list_top_collections(self, qdrant_url, headers=None, prefix="germany_v", top_n=2):
        """Returns the names of the `top_n` collections with the highest numeric suffix for a given prefix.

        Args:
            qdrant_url (str): Qdrant base URL.
            headers (dict, optional): HTTP headers with optional API key.
            prefix (str): The prefix of the collections, e.g. "germany_v".
            top_n (int): How many collections with highest number should be returned.

        Returns:
            list: List of `top_n` collection names with highest index, or empty list on error.

        """
        url = f"{qdrant_url}/collections"
        try:
            response = requests.get(url, headers=headers, timeout=30)
            print(response)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            log.info(f"Error retrieving collections: {e}")
            return []

        collections = response.json().get("result", {}).get("collections", [])
        collection_names = [col.get("name") for col in collections]

        # Filter by matching prefix and extract numeric suffixes
        pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
        matching = []
        for name in collection_names:
            match = pattern.match(name)
            if match:
                number = int(match.group(1))
                matching.append((number, name))

        # Sort descending by number and take top N
        matching.sort(reverse=True)
        top_collections = [name for _, name in matching[:top_n]]

        return top_collections

    def _get_collection_info(self, collection_name):
        """Get collection information with timeout handling."""
        response = requests.get(f"{self.settings.QDRANT_URL}/collections/{collection_name}", headers=self.headers, timeout=30)
        return response.json() if response.status_code == 200 else None

    def _calc_tlsh(self, text):
        """Safely calculate the TLSH hash of a given text if it meets basic criteria.

        Args:
            text (str): The input text to be hashed.

        Returns:
            str or None: The TLSH hash string, or None if input is invalid or hashing fails.

        """
        if not text:
            log.debug("TLSH skipped: Empty or None input.")
            return None

        if not isinstance(text, str):
            log.warning(f"TLSH skipped: Expected string but got {type(text)}")
            return None

        if len(text) <= 50:
            log.debug("TLSH skipped: Text too short (<= 50 characters).")
            return None

        try:
            return tlsh.hash(text.encode("utf-8"))
        except UnicodeEncodeError as e:
            log.error(f"TLSH Unicode encoding error: {e}")
        except tlsh.TlshException as e:
            log.error(f"TLSH hashing error: {e}")

        return None

    def _get_all_points_as_df(self, collection_name):
        """Fetch all points from a collection as DataFrame."""
        all_rows = []
        offset = None
        limit = 100

        collection_info = self._get_collection_info(collection_name)
        total_points = collection_info.get("result", {}).get("vectors_count") if collection_info else 0

        with tqdm(total=total_points, desc=f"Fetching {collection_name}") as pbar:
            while True:
                payload = {"limit": limit, "with_payload": True, "with_vector": True}
                if offset:
                    payload["offset"] = offset

                response = requests.post(
                    f"{self.settings.QDRANT_URL}/collections/{collection_name}/points/scroll",
                    headers=self.headers,
                    json=payload,
                    timeout=60,
                )

                if not response.ok:
                    break

                data = response.json()
                points = data["result"]["points"]
                if not points:
                    break

                for point in points:
                    row = point.get("payload", {})
                    row["id"] = point["id"]
                    row["tlsh"] = row.get("text_tlsh_hash") or self._calc_tlsh(row.get("text"))
                    all_rows.append(row)

                offset = data["result"].get("next_page_offset")
                pbar.update(len(points))
                if not offset:
                    break

        return pd.DataFrame(all_rows)

    def _fuzzy_tlsh_matches(self, df, tlsh_col, max_diff):
        """Find fuzzy TLSH matches using enumerate for better performance."""
        matches = []
        hashes = df[tlsh_col].dropna()
        idx_hash = list(hashes.items())

        for i, (idx_a, hash_a) in enumerate(idx_hash):
            for j in range(i + 1, len(idx_hash)):
                idx_b, hash_b = idx_hash[j]
                try:
                    diff = tlsh.diff(hash_a, hash_b)
                    if diff is not None and diff <= max_diff:
                        matches.append((idx_a, idx_b, diff))
                except tlsh.TlshException:
                    continue
        return matches

    def _diff_snippet(self, a, b, context=20):
        """Generate a diff snippet between two texts."""
        sm = difflib.SequenceMatcher(None, a, b)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != "equal":
                start_a = max(i1 - context, 0)
                end_a = min(i2 + context, len(a))
                start_b = max(j1 - context, 0)
                end_b = min(j2 + context, len(b))
                snippet_a = a[start_a:end_a]
                snippet_b = b[start_b:end_b]
                return f"a:[{snippet_a}] | b:[{snippet_b}]"
        return ""

    def _suspicious_cases_analysis(self, df, matches, text_col):
        """Analyze suspicious cases from fuzzy matches."""
        suspicious = []
        for idx_a, idx_b, diff in matches:
            text_a = str(df.loc[idx_a, text_col])
            text_b = str(df.loc[idx_b, text_col])
            fuzzval = fuzz.ratio(text_a, text_b)
            if fuzzval < 100:
                suspicious.append(
                    {
                        "index_a": idx_a,
                        "point_index_a": idx_a + 1,
                        "index_b": idx_b,
                        "point_index_b": idx_b + 1,
                        "text_a": text_a,
                        "text_b": text_b,
                        "fuzz_ratio": fuzzval,
                        "tlsh_diff": diff,
                        "diff": self._diff_snippet(text_a, text_b),
                    }
                )
        return suspicious

    def _analyze_extra_docs_detail(self, df_base, df_extra, text_col, threshold):
        """Analyze extra documents with optimized ratio calculation."""
        results = []
        for idx, extra_row in df_extra.iterrows():
            extra_text = str(extra_row[text_col])

            # Use max() for better performance
            ratios = [fuzz.ratio(extra_text, str(base_text)) for base_text in df_base[text_col]]
            best_ratio = max(ratios) if ratios else 0

            is_truly_new = best_ratio < threshold
            results.append(
                {
                    "index": idx,
                    "point_index": idx + 1,
                    "best_ratio": best_ratio,
                    "is_truly_new": is_truly_new,
                    "diff": self._diff_snippet(extra_text, str(df_base[text_col].iloc[0])),
                }
            )
        return results

    def _gpt_contradict_check(self, doc1, doc2, idx1=None, idx2=None):
        """Check for contradictions between two documents using GPT."""
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
    - If you use the word 'contradiction', you MUST quote the exact sentences or phrases from both documents that contradict each other,
        and explain why they are contradictory.
    - If there is no contradiction, check if the documents are redundant. Only use 'redundancy' or 'redundant' if the information
        is truly duplicated and the two documents share the same exact semantic information.

    **YOUR TASKS:**
    1. Decide if the two documents are in factual contradiction. If yes, quote the exact contradictory statements
        and explain the contradiction.
    2. If there is NO contradiction, check if the documents are redundant (i.e., only if they contain
        the exact semantic same information). If so, state which document is redundant and what is duplicated.
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
                    {
                        "role": "system",
                        "content": "You are a critical and precise analyst for technical documents. "
                        'Only use the word "contradiction" if you can literally quote two sentences from the documents that directly '
                        "contradict each other. Otherwise, do not use this word.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            result_text = response.choices[0].message.content.strip()
            print(result_text)
            return {
                "index_a": idx1,
                "index_b": idx2,
                "gpt_analysis": result_text,
                "contradiction_found": "contradiction" in result_text.lower(),
            }

        except openai.OpenAIError as e:
            return {"index_a": idx1, "index_b": idx2, "gpt_analysis": f"OpenAI API error: {e}", "contradiction_found": False}

        except httpx.RequestError as e:
            return {"index_a": idx1, "index_b": idx2, "gpt_analysis": f"HTTP error: {e}", "contradiction_found": False}

        except socket.timeout:
            return {"index_a": idx1, "index_b": idx2, "gpt_analysis": "Socket timeout error", "contradiction_found": False}

        except ValueError as e:
            return {"index_a": idx1, "index_b": idx2, "gpt_analysis": f"Value error: {e}", "contradiction_found": False}

    def _extract_gpt_shortform(self, gpt_result):
        """Extract short form recommendation from GPT result."""
        content = gpt_result.get("gpt_analysis", "")
        if not isinstance(content, str):
            return ""
        content_lower = content.lower()
        if "contradiction" in content_lower:
            return "contradiction"
        if "keep both" in content_lower or "redundancy" in content_lower:
            return "both"
        if "remove document 1" in content_lower:
            return "a remove"
        if "remove document 2" in content_lower:
            return "b remove"
        return ""
