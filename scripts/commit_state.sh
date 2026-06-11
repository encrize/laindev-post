#!/usr/bin/env bash
# Надёжный коммит состояния data/ при гонке нескольких воркфлоу.
# Стратегия last-writer-wins для data/*.json: наша версия пересчитывается
# поверх свежего remote — без конфликт-маркеров. Воркфлоу не падает из-за состояния.
set -u

msg="${1:-chore: update state [skip ci]}"
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
if [ "$branch" = "HEAD" ]; then
  branch="${GITHUB_REF_NAME:-main}"
fi

git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3 4 5; do
  git add data/ 2>/dev/null || true

  # Зафиксируем наши изменения, если они есть и ещё не закоммичены.
  if ! git diff --cached --quiet; then
    git commit -m "$msg" >/dev/null 2>&1 || true
  fi

  git fetch origin "$branch" >/dev/null 2>&1 || true
  if git rebase "origin/$branch" >/dev/null 2>&1; then
    if git push origin "HEAD:refs/heads/$branch" >/dev/null 2>&1; then
      echo "[commit_state] ok (попытка $attempt)"
      exit 0
    fi
    # push не прошёл (remote сдвинулся) — повторим цикл.
  else
    git rebase --abort >/dev/null 2>&1 || true
    # Берём свежий remote как базу, НАШИ файлы data/ остаются как изменения.
    git reset --mixed "origin/$branch" >/dev/null 2>&1 || true
  fi

  sleep $((RANDOM % 4 + 2))
done

echo "[commit_state] не удалось запушить состояние — оставляю на следующий запуск" >&2
exit 0
