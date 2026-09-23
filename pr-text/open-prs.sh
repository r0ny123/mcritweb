#!/bin/sh
# Pushes the reviewed branches from r0ny123/mcritweb to familiary/mcritweb and opens one pull
# request for each, titled and described from the files in pr-text/.
#
# Needs git and the GitHub CLI, logged in as someone who may push branches to
# familiary/mcritweb (`gh auth status`; `gh auth setup-git` lets git push with the same login).
# Run it from an empty directory. DRY_RUN=1 prints what it would do and changes nothing.
# A branch that already has an open pull request is skipped, so it is safe to run again.
set -eu

FORK=https://github.com/r0ny123/mcritweb
UPSTREAM=familiary/mcritweb
TEXTS=claude/admiring-turing-4ihzfx

# branch on the fork | PR text | issue text to file first, if the PR needs a new issue |
# base branch, if the PR is stacked on another one of this list rather than on master
BRANCHES='
fix/182-cross-compare-lazy-tabs|fix-182-cross-compare-lazy-tabs.md|
fix/183-poll-job-status|fix-183-poll-job-status.md|
fix/184-unique-blocks-cache|fix-184-unique-blocks-cache.md|
fix/186-function-diff-cache|fix-186-function-diff-cache.md|
fix/187-link-hunt-clusters|fix-187-link-hunt-clusters.md|
fix/188-diagram-drawing|fix-188-diagram-drawing.md|
fix/189-explore-sleeps|fix-189-explore-sleeps.md|
fix/190-request-row-reads|fix-190-request-row-reads.md|
fix/191-serial-entry-fetches|fix-191-serial-entry-fetches.md|
fix/192-bounded-collections|fix-192-bounded-collections.md|
fix/193-jobs-for-sample-once|fix-193-jobs-for-sample-once.md|
fix/194-result-view-passes|fix-194-result-view-passes.md|
fix/197-link-hunt-links|fix-197-link-hunt-links.md|
fix/199-users-page-single-pass|fix-199-users-page-single-pass.md|
fix/200-api-passthrough-bytes|fix-200-api-passthrough-bytes.md|
fix/202-result-cache-size|fix-202-result-cache-size.md|
fix/206-admin-account-handlers|fix-206-admin-account-handlers.md|
fix/207-check-then-fetch|fix-207-check-then-fetch.md|
fix/linkhunt-empty-family-count|fix-linkhunt-empty-family-count.md|issue-new-linkhunt-family-count.md
'

run() {
    if [ "${DRY_RUN:-0}" = 1 ]; then echo "would run: $*"; else "$@"; fi
}

[ -d mcritweb ] || git clone --quiet "https://github.com/$UPSTREAM" mcritweb
cd mcritweb
git fetch --quiet "$FORK" "+refs/heads/$TEXTS:refs/remotes/fork/texts"
mkdir -p ../texts
for file in $(git ls-tree --name-only refs/remotes/fork/texts pr-text/); do
    git show "refs/remotes/fork/texts:$file" > "../texts/$(basename "$file")"
done

echo "$BRANCHES" | while IFS='|' read -r branch text issue onto; do
    [ -n "$branch" ] || continue
    if [ "$(gh pr list --repo "$UPSTREAM" --head "$branch" --state open --json number --jq length)" != 0 ]; then
        echo "skip $branch: it already has an open pull request"
        continue
    fi
    git fetch --quiet "$FORK" "+refs/heads/$branch:refs/remotes/fork/$branch"
    if [ -z "$onto" ]; then
        onto=master
        base=$(git merge-base "refs/remotes/fork/$branch" origin/master)
    else
        # a stacked branch is one commit on its base branch, which an earlier row pushed
        git fetch --quiet "$FORK" "+refs/heads/$onto:refs/remotes/fork/$onto"
        base=$(git rev-parse "refs/remotes/fork/$onto")
    fi
    if [ "$(git rev-list --count "$base..refs/remotes/fork/$branch")" != 1 ] || \
       [ "$(git rev-parse "refs/remotes/fork/$branch^")" != "$base" ]; then
        echo "stop: $branch is not one commit on $onto" >&2
        exit 1
    fi
    run git push origin "refs/remotes/fork/$branch:refs/heads/$branch"

    title=$(sed -n '1s/^Title: //p' "../texts/$text")
    tail -n +3 "../texts/$text" > ../body.md
    if [ -n "$issue" ]; then
        issue_title=$(sed -n '1s/^Title: //p' "../texts/$issue")
        tail -n +3 "../texts/$issue" > ../issue.md
        if [ "${DRY_RUN:-0}" = 1 ]; then
            number=NNN
            echo "would file issue: $issue_title"
        else
            number=$(gh issue create --repo "$UPSTREAM" --title "$issue_title" --body-file ../issue.md | sed 's#.*/##')
        fi
        # the PR text refers to the draft by its file name until the issue exists
        sed "s|#NNN (the issue in \`pr-text/$issue\`, once it is filed)|#$number|" ../body.md > ../body.tmp
        mv ../body.tmp ../body.md
    fi
    run gh pr create --repo "$UPSTREAM" --base "$onto" --head "$branch" --title "$title" --body-file ../body.md
done
