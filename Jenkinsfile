pipeline {
    agent none

    options {
        skipDefaultCheckout(true)
        disableConcurrentBuilds()
        buildDiscarder(logRotator(
            numToKeepStr: '20',
            artifactNumToKeepStr: '3'
        ))
        timeout(time: 6, unit: 'HOURS')
    }

    parameters {
        booleanParam(
            name: 'BUILD_DESKTOP',
            defaultValue: false,
            description: 'Build and archive the native Windows, Linux, and macOS packages.'
        )
        booleanParam(
            name: 'PUBLISH_RELEASE',
            defaultValue: false,
            description: 'Publish the selected immutable tag to GitHub Releases. This also enables all native builds.'
        )
        string(
            name: 'RELEASE_TAG',
            defaultValue: '',
            description: 'Optional existing vMAJOR.MINOR.PATCH tag. Required for publishing.',
            trim: true
        )
    }

    environment {
        CI = 'true'
        GH_REPO = 'dirhamtriyadi/spade65-non-qmk'
        PIP_DISABLE_PIP_VERSION_CHECK = '1'
        PIP_NO_INPUT = '1'
        PYTHONUNBUFFERED = '1'
    }

    stages {
        stage('Resolve immutable source') {
            agent { label 'linux' }
            options {
                timeout(time: 15, unit: 'MINUTES')
            }
            steps {
                deleteDir()
                checkout scm
                script {
                    def releaseTag = params.RELEASE_TAG.trim()
                    if (releaseTag && !(releaseTag ==~ /^v\d+\.\d+\.\d+$/)) {
                        error('RELEASE_TAG must have the exact form vMAJOR.MINOR.PATCH')
                    }
                    if (params.PUBLISH_RELEASE && !releaseTag) {
                        error('PUBLISH_RELEASE requires RELEASE_TAG')
                    }
                    if (params.PUBLISH_RELEASE && env.CHANGE_ID?.trim()) {
                        error('Publishing is forbidden from pull-request jobs')
                    }
                    if (
                        params.PUBLISH_RELEASE
                        && env.BRANCH_NAME?.trim()
                        && env.BRANCH_NAME != 'main'
                    ) {
                        error('Publishing is allowed only from the main branch job')
                    }

                    if (releaseTag) {
                        sh '''#!/usr/bin/env bash
set -euo pipefail
git fetch --force origin \
  "refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"
git show-ref --verify --quiet "refs/tags/${RELEASE_TAG}"
'''
                        env.SOURCE_COMMIT = sh(
                            returnStdout: true,
                            script: '''#!/usr/bin/env bash
set -euo pipefail
git rev-parse "refs/tags/${RELEASE_TAG}^{commit}"
'''
                        ).trim()
                    } else {
                        env.SOURCE_COMMIT = sh(
                            returnStdout: true,
                            script: 'git rev-parse HEAD'
                        ).trim()
                    }

                    sh '''#!/usr/bin/env bash
set -euo pipefail
git checkout --detach "${SOURCE_COMMIT}"
test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"
command -v python3.13
if [[ -n ${RELEASE_TAG} ]]; then
  python3.13 packaging/check_version.py "${RELEASE_TAG}"
else
  python3.13 packaging/check_version.py --print-version
fi
'''
                    echo "Resolved source commit ${env.SOURCE_COMMIT}"
                }
            }
            post {
                always {
                    deleteDir()
                }
            }
        }

        stage('Release preflight') {
            when {
                beforeAgent true
                expression { params.PUBLISH_RELEASE }
            }
            agent { label 'linux' }
            options {
                timeout(time: 10, unit: 'MINUTES')
            }
            steps {
                withCredentials([
                    string(
                        credentialsId: 'spade65-github-token',
                        variable: 'GH_TOKEN'
                    )
                ]) {
                    sh '''#!/usr/bin/env bash
set -euo pipefail
command -v gh
state=$(gh release view "${RELEASE_TAG}" --json isDraft \
  --jq .isDraft 2>/dev/null || printf 'missing')
if [[ $state == false ]]; then
  echo "Release ${RELEASE_TAG} is already published; refusing overwrite." >&2
  exit 1
fi
'''
                }
            }
        }

        stage('Cross-platform tests') {
            matrix {
                axes {
                    axis {
                        name 'PLATFORM'
                        values 'linux', 'windows', 'macos'
                    }
                    axis {
                        name 'PYTHON_VERSION'
                        values '3.10', '3.13'
                    }
                }
                agent { label "${PLATFORM}" }
                options {
                    timeout(time: 45, unit: 'MINUTES')
                }
                stages {
                    stage('Unit and static checks') {
                        steps {
                            deleteDir()
                            checkout scm
                            script {
                                if (isUnix()) {
                                    sh '''#!/usr/bin/env bash
set -euo pipefail
if [[ -n ${RELEASE_TAG} ]]; then
  git fetch --force origin \
    "refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"
fi
git checkout --detach "${SOURCE_COMMIT}"
test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"

python_bin="python${PYTHON_VERSION}"
command -v "$python_bin"
"$python_bin" -m venv .jenkins-venv
.jenkins-venv/bin/python -m pip install --upgrade pip
.jenkins-venv/bin/python -m pip install -e '.[dev]'
.jenkins-venv/bin/python -m unittest discover -v
.jenkins-venv/bin/python -m compileall -q \
  spade65 spade65ctl.py packaging tests tools
.jenkins-venv/bin/python tools/format_web.py --check
node --check spade65/web/layout-state.js
node --check spade65/web/app.js
node tests/layout_state.test.js
'''
                                } else {
                                    bat '''@echo off
if not "%RELEASE_TAG%"=="" (
  git fetch --force origin "refs/tags/%RELEASE_TAG%:refs/tags/%RELEASE_TAG%"
  if errorlevel 1 exit /b 1
)
git checkout --detach "%SOURCE_COMMIT%"
if errorlevel 1 exit /b 1
for /f %%C in ('git rev-parse HEAD') do set "ACTUAL_COMMIT=%%C"
if /I not "%ACTUAL_COMMIT%"=="%SOURCE_COMMIT%" exit /b 1

py -%PYTHON_VERSION% -m venv .jenkins-venv
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m pip install -e ".[dev]"
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m unittest discover -v
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m compileall -q spade65 spade65ctl.py packaging tests tools
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe tools\format_web.py --check
if errorlevel 1 exit /b 1
node --check spade65\web\layout-state.js
if errorlevel 1 exit /b 1
node --check spade65\web\app.js
if errorlevel 1 exit /b 1
node tests\layout_state.test.js
if errorlevel 1 exit /b 1
'''
                                }
                            }
                        }
                        post {
                            always {
                                deleteDir()
                            }
                        }
                    }
                }
            }
        }

        stage('Native packages') {
            when {
                beforeAgent true
                expression {
                    params.BUILD_DESKTOP || params.PUBLISH_RELEASE
                }
            }
            failFast true
            parallel {
                stage('Windows package') {
                    agent { label 'windows' }
                    options {
                        timeout(time: 2, unit: 'HOURS')
                    }
                    steps {
                        deleteDir()
                        checkout scm
                        bat '''@echo off
if not "%RELEASE_TAG%"=="" (
  git fetch --force origin "refs/tags/%RELEASE_TAG%:refs/tags/%RELEASE_TAG%"
  if errorlevel 1 exit /b 1
)
git checkout --detach "%SOURCE_COMMIT%"
if errorlevel 1 exit /b 1
for /f %%C in ('git rev-parse HEAD') do set "ACTUAL_COMMIT=%%C"
if /I not "%ACTUAL_COMMIT%"=="%SOURCE_COMMIT%" exit /b 1

py -3.13 -m venv .jenkins-venv
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m pip install -r requirements-build.txt ".[cross-platform,desktop]"
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m pip check
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe -m pip freeze
if errorlevel 1 exit /b 1
.jenkins-venv\Scripts\python.exe packaging\build.py
if errorlevel 1 exit /b 1
if not exist "artifacts\Spade65-Windows-x64.zip" exit /b 1
for %%F in ("artifacts\Spade65-Windows-x64.zip") do if %%~zF LEQ 0 exit /b 1
'''
                        stash(
                            name: 'windows-release',
                            includes: 'artifacts/Spade65-Windows-x64.zip',
                            useDefaultExcludes: false
                        )
                    }
                    post {
                        always {
                            deleteDir()
                        }
                    }
                }

                stage('Linux package') {
                    agent { label 'linux' }
                    options {
                        timeout(time: 2, unit: 'HOURS')
                    }
                    environment {
                        SPADE65_STRICT_LINUX_LEGAL = '1'
                    }
                    steps {
                        deleteDir()
                        checkout scm
                        sh '''#!/usr/bin/env bash
set -euo pipefail
if [[ -n ${RELEASE_TAG} ]]; then
  git fetch --force origin \
    "refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"
fi
git checkout --detach "${SOURCE_COMMIT}"
test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"
test "$(uname -m)" = x86_64
. /etc/os-release
test "$ID" = ubuntu
test "$VERSION_ID" = 22.04
for package in \
  libstdc++6 libgcc-s1 libgbm1 libfontconfig1 libfreetype6 \
  libexpat1 libx11-6 libx11-xcb1 libasound2 libegl1 libgl1 \
  libxcb-shape0 libxcb-image0 libxcb-xkb1 libxcb-icccm4 \
  libxkbcommon-x11-0 libxcb-util1 libxcb-cursor0 libxcb-keysyms1 \
  libxcb-render-util0; do
  dpkg-query -W -f='${db:Status-Abbrev}\n' "$package" | grep -q '^ii '
done

python3.13 -m venv .jenkins-venv
.jenkins-venv/bin/python -m pip install \
  -r requirements-build.txt ".[desktop]"
.jenkins-venv/bin/python -m pip check
.jenkins-venv/bin/python -m pip freeze
.jenkins-venv/bin/python packaging/build.py
test -s artifacts/Spade65-Linux-x86_64.AppImage
'''
                        stash(
                            name: 'linux-release',
                            includes: 'artifacts/Spade65-Linux-x86_64.AppImage',
                            useDefaultExcludes: false
                        )
                    }
                    post {
                        always {
                            deleteDir()
                        }
                    }
                }

                stage('macOS package') {
                    agent { label 'macos' }
                    options {
                        timeout(time: 2, unit: 'HOURS')
                    }
                    environment {
                        ARCHFLAGS = '-arch x86_64 -arch arm64'
                        MACOSX_DEPLOYMENT_TARGET = '11.0'
                    }
                    steps {
                        deleteDir()
                        checkout scm
                        sh '''#!/usr/bin/env bash
set -euo pipefail
if [[ -n ${RELEASE_TAG} ]]; then
  git fetch --force origin \
    "refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"
fi
git checkout --detach "${SOURCE_COMMIT}"
test "$(git rev-parse HEAD)" = "${SOURCE_COMMIT}"

macos_python=${SPADE65_MACOS_PYTHON:-/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13}
test -x "$macos_python"
resolved_python=$("$macos_python" -c \
  'import pathlib, sys; print(pathlib.Path(sys.executable).resolve())')
file "$resolved_python"
lipo "$resolved_python" -verify_arch x86_64 arm64
"$macos_python" -m venv .jenkins-venv
build_python="$PWD/.jenkins-venv/bin/python"
"$build_python" -m pip install -r requirements-build.txt
"$build_python" -m pip install --no-build-isolation ".[desktop]"
"$build_python" -m pip check
"$build_python" -m pip freeze
SPADE65_BUILD_PYTHON="$build_python" \
  bash packaging/build_macos_hidapi.sh
if [[ -n ${RELEASE_TAG} ]]; then
  export SPADE65_VERSION=${RELEASE_TAG#v}
fi
"$build_python" packaging/build.py
test -s artifacts/Spade65-macOS-universal.dmg
'''
                        stash(
                            name: 'macos-release',
                            includes: 'artifacts/Spade65-macOS-universal.dmg',
                            useDefaultExcludes: false
                        )
                    }
                    post {
                        always {
                            deleteDir()
                        }
                    }
                }
            }
        }

        stage('Archive packages') {
            when {
                beforeAgent true
                expression {
                    params.BUILD_DESKTOP || params.PUBLISH_RELEASE
                }
            }
            agent { label 'linux' }
            options {
                timeout(time: 20, unit: 'MINUTES')
            }
            steps {
                deleteDir()
                unstash 'windows-release'
                unstash 'linux-release'
                unstash 'macos-release'
                sh '''#!/usr/bin/env bash
set -euo pipefail
test -s artifacts/Spade65-Windows-x64.zip
test -s artifacts/Spade65-Linux-x86_64.AppImage
test -s artifacts/Spade65-macOS-universal.dmg
test "$(find artifacts -maxdepth 1 -type f | wc -l)" -eq 3
sha256sum \
  artifacts/Spade65-Windows-x64.zip \
  artifacts/Spade65-Linux-x86_64.AppImage \
  artifacts/Spade65-macOS-universal.dmg
'''
                archiveArtifacts(
                    artifacts: 'artifacts/*',
                    fingerprint: true,
                    onlyIfSuccessful: true
                )
            }
            post {
                always {
                    deleteDir()
                }
            }
        }

        stage('Publish GitHub release') {
            when {
                beforeAgent true
                expression { params.PUBLISH_RELEASE }
            }
            agent { label 'linux' }
            options {
                timeout(time: 20, unit: 'MINUTES')
            }
            steps {
                deleteDir()
                checkout scm
                unstash 'windows-release'
                unstash 'linux-release'
                unstash 'macos-release'
                sh '''#!/usr/bin/env bash
set -euo pipefail
command -v gh
origin=$(git remote get-url origin)
case $origin in
  git@github.com:dirhamtriyadi/spade65-non-qmk.git|\
  https://github.com/dirhamtriyadi/spade65-non-qmk|\
  https://github.com/dirhamtriyadi/spade65-non-qmk.git|\
  ssh://git@github.com/dirhamtriyadi/spade65-non-qmk.git) ;;
  *)
    echo "Unexpected release remote: $origin" >&2
    exit 1
    ;;
esac
git fetch --force origin \
  "refs/tags/${RELEASE_TAG}:refs/tags/${RELEASE_TAG}"
actual_commit=$(git rev-parse "refs/tags/${RELEASE_TAG}^{commit}")
if [[ $actual_commit != "$SOURCE_COMMIT" ]]; then
  echo "Tag ${RELEASE_TAG} moved after validation; refusing publish." >&2
  exit 1
fi
python3.13 packaging/check_version.py "${RELEASE_TAG}"
test -s artifacts/Spade65-Windows-x64.zip
test -s artifacts/Spade65-Linux-x86_64.AppImage
test -s artifacts/Spade65-macOS-universal.dmg
test "$(find artifacts -maxdepth 1 -type f | wc -l)" -eq 3
'''
                withCredentials([
                    string(
                        credentialsId: 'spade65-github-token',
                        variable: 'GH_TOKEN'
                    )
                ]) {
                    sh '''#!/usr/bin/env bash
set -euo pipefail
state=$(gh release view "${RELEASE_TAG}" --json isDraft \
  --jq .isDraft 2>/dev/null || printf 'missing')
if [[ $state == false ]]; then
  echo "Release ${RELEASE_TAG} is already published; refusing overwrite." >&2
  exit 1
fi
if [[ $state == missing ]]; then
  gh release create "${RELEASE_TAG}" --verify-tag --generate-notes \
    --title "Spade65 ${RELEASE_TAG}" --draft
fi
draft_state=$(gh release view "${RELEASE_TAG}" --json isDraft \
  --jq .isDraft)
if [[ $draft_state != true ]]; then
  echo 'Release must remain a draft until every asset is verified.' >&2
  exit 1
fi
unexpected=$(gh release view "${RELEASE_TAG}" --json assets --jq \
  '.assets[].name | select(. != "Spade65-Windows-x64.zip" and . != "Spade65-Linux-x86_64.AppImage" and . != "Spade65-macOS-universal.dmg")')
if [[ -n $unexpected ]]; then
  echo 'Draft contains unexpected assets; refusing destructive cleanup:' >&2
  echo "$unexpected" >&2
  exit 1
fi
gh release upload "${RELEASE_TAG}" \
  artifacts/Spade65-Windows-x64.zip \
  artifacts/Spade65-Linux-x86_64.AppImage \
  artifacts/Spade65-macOS-universal.dmg \
  --clobber
asset_count=$(gh release view "${RELEASE_TAG}" --json assets \
  --jq '.assets | length')
test "$asset_count" -eq 3
gh release edit "${RELEASE_TAG}" --draft=false
'''
                }
            }
            post {
                always {
                    deleteDir()
                }
            }
        }
    }
}
