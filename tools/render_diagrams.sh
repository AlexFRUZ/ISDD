#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
: "${PLANTUML_JAR:?Вкажіть шлях до plantuml.jar у змінній PLANTUML_JAR}"
find lab* iz -name '*.puml' -print0 | xargs -0 java -Djava.awt.headless=true -jar "$PLANTUML_JAR" -charset UTF-8 -tpng
