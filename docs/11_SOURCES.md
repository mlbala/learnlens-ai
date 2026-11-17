# 11 — Verified Primary Sources and Research Reading List

Checked for relevance as of **2026-11-16**. Follow current vendor documentation at implementation time; model names/pricing/quotas can change. The links are reference materials, not endorsed external code dependencies.

## Official development references

1. YouTube playlist items: https://developers.google.com/youtube/data/reference/rest/v3/playlistItems/list — playlist pagination, 50 items/page.
2. YouTube caption download: https://developers.google.com/youtube/data/reference/rest/v3/captions/download — **must have permission to edit video**.
3. YouTube developer policy: https://developers.google.com/youtube/terms/developer-policies — authorized access/handling requirements.
4. YouTube IFrame Player: https://developers.google.com/youtube/iframe_api_reference — source playback/time seek.
5. OpenAI text generation: https://developers.openai.com/api/docs/guides/text — Responses API.
6. OpenAI embeddings: https://developers.openai.com/api/docs/guides/embeddings — text embedding choices and dimensions.
7. Gemini Interactions: https://aistudio.google.com/docs/interactions-overview — recommended new API, `generateContent` remains supported.
8. Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output — server JSON Schema and validation.
9. Gemini embeddings: https://ai.google.dev/gemini-api/docs/embeddings — text and multimodal embedding options.
10. DeepSeek getting started: https://api-docs.deepseek.com/guides/codex — compatible API and model identifiers.
11. DeepSeek JSON mode: https://api-docs.deepseek.com/guides/json_mode/ — JSON output caveats/empty responses.
12. DeepSeek models and pricing: https://api-docs.deepseek.com/quick_start/pricing/ — verify before calculating costs.
13. Qdrant hybrid search: https://qdrant.tech/documentation/hybrid-queries/ — RRF, dense + BM25/sparse retrieval.
14. Qdrant multi-tenancy: https://qdrant.tech/documentation/deploy-and-scale/multitenant-search/ — filter and keyword index patterns.
15. Cursor project rules: https://docs.cursor.com/context/rules-for-ai — `.cursor/rules/*.mdc` and rule formats.
16. Cursor usage/pricing: https://cursor.com/pricing — varies by plan; view actual account dashboard.
17. OWASP LLM Top 10: https://genai.owasp.org/llm-top-10/ — threat modeling and release gates.
18. OWASP AI security tests: https://owasp.github.io/DevSecOpsGuideline/2-Process/2-4-Test/2-4-6-AI-LLM-Application-Security-Testing/ — adversarial test patterns.

## Academic foundations

1. Sarthi et al., **RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval**, 2024: https://arxiv.org/abs/2401.18059. Takeaway: hierarchical chunk/summary representations can help retrieve both fine and broad evidence.
2. Jeong et al., **VideoRAG: Retrieval-Augmented Generation over Video Corpus**, Findings of ACL 2025: https://aclanthology.org/2025.findings-acl.1096/. Takeaway: multimodal video retrieval should preserve visual and speech evidence where legally available.
3. Fu et al., **Video-MME: The First-Ever Comprehensive Evaluation Benchmark of Multi-modal LLMs in Video Analysis**, CVPR 2025: https://arxiv.org/abs/2405.21075. Takeaway: rigorous video QA testing should not assume transcripts contain every visual detail.
4. **LongVideoBench**, 2024: https://arxiv.org/abs/2407.15754. Takeaway: long video reasoning is challenging and needs retrieval/evaluation across temporal evidence.

## Interpretation cautions

These sources justify design hypotheses, not proof that LearnLens will improve educational performance. In particular: VideoRAG research is a multimodal system; LearnLens MVP is transcript-first. No paper endorses ignoring media permissions. Report evaluation results only when actually run.
