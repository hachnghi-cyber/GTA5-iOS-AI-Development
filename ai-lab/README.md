# GTA V iOS — AI Development Lab (100 Roles)

The registry defines 100 specialist role configurations in ten groups. These do not represent 100 independently running models.

## Automatic checks
- Relevant push and pull requests: Python compilation, unit tests, specialist routing and downloadable JSON artifact.
- Nightly checks: scheduled static CI on the default branch after merging.
- Manual custom task: Actions > GTA AI Lab - Automated CI > Run workflow (available after workflow is merged into the default branch).
- Optional read-only AI review: available only after setting Actions variable ENABLE_CODEX_REVIEW=true and secret OPENAI_API_KEY; incurs possible API charges. The AI does not push code or merge changes.

## Usage
python ai-lab/dispatcher.py plan --task "SIGSEGV crash after Menyoo vehicle spawn" --top 5

python ai-lab/dispatcher.py run --task "Analyze iOS crash" --top 2

The optional run command needs an installed and authenticated Codex CLI and invokes at most three sequential read-only roles. It does not activate 100 parallel agents.

## Safety and scope
This initial version automates specialist selection and CI, not GTA V IPA building, resigning, binary patching, or hardware validation. Store source code and patches in feature branches. Use pull requests and checks before merging. Never expose game assets, API keys or certificates.
