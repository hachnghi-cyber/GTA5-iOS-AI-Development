# GTA V iOS Roleplay — Autonomous Coding Setup

This workflow implements **bounded unattended source coding**, not an infinitely running AI model. It starts on an hourly GitHub Actions schedule (19th minute of each hour, UTC) and can be manually dispatched, AFTER merging its Pull Request to main.

## How it works
1. `key_check` runs only when `ENABLE_RP_AUTOCODE=true`. It checks whether the secret `OPENAI_API_KEY` exists without outputting the secret.
2. `reserve` reads the three reviewed tasks from `ai-lab/autocode/tasks.json` and reserves ONE task on an `autocode/rp-...` branch. A reserved branch blocks repeat paid executions for that task, even if AI or checks fail.
3. `code` runs `openai/codex-action@v1` with a scoped `:workspace` permission profile, no GitHub write token and no direct access to game binaries. It emits a patch artifact in an unprivileged job.
4. `submit` obtains a separate GitHub token, applies only a patch changing allowed text files, blocks binaries/workflows/credentials, runs unit tests and state validation, then commits into the reserved branch and creates a **draft PR**. It dispatches the existing AI Lab CI on the new branch.
5. If no approved tasks remain, the scheduled run skips without API calls. An unattended PR is **never auto-merged or released**.

## Activate on GitHub (manual account actions required)
- Review and merge the feature PR first.
- Go to repository **Settings → Secrets and variables → Actions**:
  - Under Secrets add a repository secret named `OPENAI_API_KEY` (requires API account/billing; ChatGPT subscription alone does not substitute for API access).
  - Under Variables add `ENABLE_RP_AUTOCODE` with value `true`.
- Go to **Settings → Actions → General → Workflow permissions** and enable **Allow GitHub Actions to create and approve pull requests**. This is needed for `gh pr create`; automated merging and approving are not used by the workflow.
- Use **Actions → GTA RP - Autonomous Codex Draft PR → Run workflow** to try one approved task, or let the next hourly run select it.

Do not paste API keys into chat, code, Issues or PRs. Configure a hard API billing budget in your OpenAI API account. One scheduled attempt consumes API credits based on model usage. This workflow caps its reviewed queue at 3 tasks, one selected per run; extending the queue needs a reviewed commit.

## Reports and failures
- A successful run creates `autocode/rp-...` branch and draft PR, with CI logs.
- If AI cannot safely change code, or validation/PR creation fails, **the reservation remains** so the next hour cannot quietly bill the same task again. Inspect the failed run and branch manually before deciding whether to retry with a new task ID.
- A failed workflow does not mean changes were merged. If GitHub account settings block PR creation, the reserved branch may contain code but no PR.
- `GTA RP - Continuous Source Watch` and ChatGPT hourly automation continue independently.
- Native engine callback/transport correctness and gameplay on iPhone still require authorized IPA, integration evidence and device logs.
- Turn off spending immediately by setting `ENABLE_RP_AUTOCODE=false`, or disable this GitHub workflow.

## Editable source boundaries
Permitted: `police-rp/`, `ai-lab/tests/`, `ai-lab/projects/roleplay-ios/`, excluding immutable baselines. No `.github/`, source binary archives, signing keys or IPA artifacts.
The patch guard enforces file types, maximum 12 files and 128 KiB patch size. All resulting changes must be reviewed before merge.
