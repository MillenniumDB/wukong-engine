"""text-embedding-3-small behind the slice of the SentenceTransformer interface that KGGen and EDC
use, so that both run with the embedder of LightRAG and GraphRAG instead of a local model.

    encode(text | [texts], prompt_name=None, show_progress_bar=..., ...) -> np.ndarray
    prompts: {}   (no instruction prompts: EDC then embeds queries as plain text)

Every string is embedded once (in-process cache) and every API call is logged to usage_log.
"""
import json
import threading
import time
from pathlib import Path

import numpy as np
import openai

MODEL = 'text-embedding-3-small'
BATCH = 512


class OpenAIEmbedder:
    def __init__(self, usage_log: Path, model: str = MODEL, stage: str = 'embed'):
        self.model, self.stage = model, stage
        self.prompts = {}
        self.usage_log = Path(usage_log)
        self.client = openai.OpenAI()
        self.cache: dict[str, np.ndarray] = {}
        self.lock = threading.Lock()

    def _embed(self, texts):
        for _ in range(8):
            try:
                t0 = time.time()
                r = self.client.embeddings.create(model=self.model, input=texts)
                break
            except openai.APIError:
                time.sleep(5)
        else:
            raise RuntimeError('embedding failed 8 times')
        with self.lock, self.usage_log.open('a') as fh:
            fh.write(json.dumps({'ts': time.time(), 'secs': round(time.time() - t0, 2), 'stage': self.stage,
                                 'model': self.model, 'input': r.usage.prompt_tokens, 'output': 0,
                                 'reasoning': 0}) + '\n')
        return [np.asarray(d.embedding, dtype=np.float32) for d in r.data]

    def encode(self, sentences, prompt_name=None, show_progress_bar=False, **kw):
        single = isinstance(sentences, str)
        items = [sentences] if single else list(sentences)
        # the API rejects empty strings; embed them as a single space
        keys = [s if s.strip() else ' ' for s in items]
        todo = list(dict.fromkeys(k for k in keys if k not in self.cache))
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            for k, v in zip(batch, self._embed(batch)):
                self.cache[k] = v
        out = np.stack([self.cache[k] for k in keys]) if keys else np.zeros((0, 1536), dtype=np.float32)
        return out[0] if single else out
