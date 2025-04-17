# SPDX-FileCopyrightText: 2025 Deutsche Telekom AG
#
# SPDX-License-Identifier: CC0-1.0
#
# https://github.com/github/gitignore/blob/main/Python.gitignore
#
# Byte-compiled / optimized / DLL files
#!/bin/bash

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
jq_run "git config --global user.email '$GIT_MAIL'"
jq_run "git config --global user.name '$GIT_USER'"
jq_run "dvc init" noexit
jq_run "dvc config core.autostage true"
jq_run "dvc config core.analytics false"
 . ${VENV}/bin/activate && wurzel generate $WURZEL_PIPELINE --data-dir $DVC_DATA_PATH > $DVC_FILE;
mkdir -p $DVC_DATA_PATH
dvc repro -q || exit 1

jq_run "git status" noexit
jq_run "dvc status" noexit
jq_run "git commit -m 'savepoint $(date +%F_%T)'" noexit
jq_run "dvc gc -n ${DVC_CACHE_HISTORY_NUMBER} -f --rev HEAD" noexit
EXT=$?
if [ -n "$PROMETHEUS__GATEWAY" ]; then
   sleep 15
   jq_run "curl -X DELETE --connect-timeout 5 ${PROMETHEUS__GATEWAY}/metrics/job/${QDRANTSTEP__COLLECTION}" noexit
fi
exit $EXT
