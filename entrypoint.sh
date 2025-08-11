#!/bin/bash
# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# https://github.com/github/gitignore/blob/main/Python.gitignore
#
# Byte-compiled / optimized / DLL files


printf "Starting Pipeline"| jq -MRcs "{message: ., level: \"INFO\",logger:\"$0\", args: {dvc_data_path:\"$DVC_DATA_PATH\", dvc_path:\"$DVC_PATH\",  dvc_file:\"$DVC_FILE\", wurzel_pipeline: \"$WURZEL_PIPELINE\"}}"

jq_run () { # Usage: jq_run "cmd with args" (noexit)
    cmd_a=($1)
    args_a=${cmd_a[@]:1}
    if result=$(eval $1 2>&1); then # Ok
        if [ -n "$result" ]; then
            printf "%s" "$result" | jq -MRcs "{message: ., level: \"INFO\",logger:\"$0/${cmd_a[0]}\", args: \"${args_a}\"}"
        fi
    else # Bad
        rc=$?
        if [[ $# -eq 1 ]]; then
            echo "$result" | jq -MRcs "{message: ., level: \"ERROR\",logger:\"$0/${cmd_a[0]}\", args: \"${args_a}\"}"
            exit $rc
        fi
        echo "$result" | jq -MRcs "{message: ., level: \"WARNING\",logger:\"$0/${cmd_a[0]}\", args: \"${args_a}\"}"
    fi
}
jq_run "git init"
jq_run "git config --global --add safe.directory /usr/app"
jq_run "git config --global user.email '${GIT_MAIL:-wurzel@example.com}'"
jq_run "git config --global user.name '${GIT_USER:-wurzel}'"
if [ -d ".dvc" ]; then
    echo "DVC already initialized" | jq -MRcs "{message: ., level: \"INFO\",logger:\"$0/dvc\", args: \"init\"}"
else
    jq_run "dvc init"
fi
wurzel generate $WURZEL_PIPELINE > $DVC_FILE || exit 1
mkdir -p $DVC_DATA_PATH
dvc repro -q || exit 1

jq_run "git status" noexit
jq_run "dvc status" noexit
jq_run "git commit -m 'savepoint $(date +%F_%T)'" noexit
jq_run "dvc gc -n ${DVC_CACHE_HISTORY_NUMBER:-5} -f --rev HEAD" noexit
EXT=$?
if [ -n "$PROMETHEUS__GATEWAY" ]; then
   sleep 15
   jq_run "curl -X DELETE --connect-timeout 5 ${PROMETHEUS__GATEWAY}/metrics/job/${QDRANTSTEP__COLLECTION}" noexit
fi
exit $EXT
