Title: Structuring Unstructured Data with BigQuery and Gemini

TL;DR: Engineering teams can perform ETL directly on unstructured data in Google Cloud Storage by leveraging BigQuery external tables and Gemini to extract queryable JSON.

Key points:
- BigQuery external tables create virtual pointers to unstructured files in Google Cloud Storage, enabling real-time access without duplicating the underlying data.
- Secure operations between BigQuery, Cloud Storage, and AI models are mediated by establishing dedicated connection service accounts.
- The built-in `ML.GENERATE_TEXT` command invokes Gemini models directly from SQL to transform raw text files into structured JSON output.
- Native BigQuery commands like `PARSE_JSON` filter out the LLM's generated metadata, cleanly extracting target entities into independent, queryable subtables.

Why it matters:
- Transforming raw unstructured files into structured formats directly within the data warehouse allows for high-speed, traditional SQL analytics while eliminating the data governance risks and storage costs of copying files.

Evidence:
- The system utilized Gemini 2.5 Flash to process unstructured text, successfully allowing a complex multi-table SQL join and ranking query to execute in approximately 300 milliseconds.

Caveat:
- BigQuery's `ML.GENERATE_TEXT` function lacks native configuration support for the Gemini API's strict JSON output toggle, meaning engineers must rely on explicit prompt engineering to enforce valid JSON generation.
