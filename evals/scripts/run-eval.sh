#!/bin/bash
promptfoo eval --config features/${1}/promptfooconfig.${2}.yaml --env-path .env "${@:3}"
