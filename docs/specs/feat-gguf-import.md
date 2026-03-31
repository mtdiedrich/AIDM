# feat: Automated GGUF Import from HuggingFace

## Goal

Allow users to pass a HuggingFace GGUF URL to `--setup` and have the system automatically download the file, import it into Ollama, and configure the game to use it.

## Current behavior

`python run.py --setup -m <model>` only pulls models from the Ollama registry. Using a custom GGUF from HuggingFace requires manual steps: downloading, writing a Modelfile, running `ollama create`.

## Target behavior

```
python run.py --setup --gguf https://huggingface.co/bartowski/TheDrummer_Anubis-Mini-8B-v1-GGUF/blob/main/TheDrummer_Anubis-Mini-8B-v1-Q8_0.gguf
```

This will:

1. Normalize the HF URL (`/blob/main/` → `/resolve/main/`) to get a direct download link.
2. Download the GGUF to `models/<filename>` with streaming progress (skip if already exists and size matches).
3. Derive a short Ollama model name from the filename (e.g. `anubis-mini-8b-v1-q8_0`).
4. Write a temporary `Modelfile` with `FROM ./path/to/file.gguf`.
5. Run `ollama create <name> -f Modelfile`.
6. Update `config.ini` with the new model name.

The `--gguf` flag is mutually exclusive with `-m` (specifying both is an error).

## Files to change

| File | Change |
|---|---|
| `aidm/setup.py` | Add `normalize_hf_url()`, `download_gguf()`, `import_gguf_to_ollama()`, `derive_model_name()`. Update `run_setup()` to accept optional `gguf_url` param. |
| `run.py` | Add `--gguf` argument. Pass to `run_setup(gguf_url=...)`. |
| `tests/test_setup.py` | Add tests for `normalize_hf_url`, `derive_model_name`, `download_gguf`, `import_gguf_to_ollama`. |

## Step-by-step instructions

### 1. `aidm/setup.py` — new functions

**`normalize_hf_url(url: str) -> str`**
- If URL contains `/blob/main/`, replace with `/resolve/main/`.
- Return the normalized URL unchanged otherwise.

**`derive_model_name(filename: str) -> str`**
- Strip `.gguf` suffix.
- Remove leading `TheDrummer_` (or any `<owner>_` prefix before the model name).
- Actually, simpler: just lowercase, replace `_` with `-`, strip `.gguf`.
- Example: `TheDrummer_Anubis-Mini-8B-v1-Q8_0.gguf` → `thedrummer-anubis-mini-8b-v1-q8-0`
  - That's ugly. Better: take the repo portion after the last `/` owner component.
  - Simplest approach: lowercase the filename stem, replace underscores with hyphens.

**`download_gguf(url: str, dest_dir: str = "models") -> str`**
- Create `dest_dir` if it doesn't exist.
- Extract filename from URL.
- If file already exists and remote `Content-Length` matches local size, skip.
- Stream download with progress (print percentage).
- Return the local file path.

**`import_gguf_to_ollama(gguf_path: str, model_name: str) -> bool`**
- Write a temporary Modelfile: `FROM <absolute_gguf_path>`.
- Run `ollama create <model_name> -f <modelfile_path>`.
- Clean up Modelfile.
- Return True on success.

**Update `run_setup()`**
- Add `gguf_url: Optional[str] = None` parameter.
- If `gguf_url` is provided:
  - Steps 1–2 (Ollama check/start) remain the same.
  - Step 3 becomes: download GGUF, import to Ollama.
  - Step 4: update config with derived model name.
- If `gguf_url` is None, existing pull-from-registry behavior.

### 2. `run.py` — new CLI arg

- Add `--gguf` argument (type=str, default=None).
- If both `--gguf` and `-m` are provided, print error and exit.
- Pass `gguf_url=args.gguf` to `run_setup()`.

### 3. Tests

In `tests/test_setup.py`:

- `TestNormalizeHfUrl`: blob→resolve conversion, already-correct URL unchanged.
- `TestDeriveModelName`: various filenames → expected short names.
- `TestDownloadGguf`: mock urllib, verify file written, verify skip on existing.
- `TestImportGgufToOllama`: mock subprocess, verify Modelfile written and cleaned up.

## Out of scope

- Supporting non-HuggingFace URLs (direct HTTP works if the URL is already a download link).
- Deleting the GGUF after import (user may want to keep it).
- Changing existing Ollama-registry pull behavior.
- Any UI changes.
