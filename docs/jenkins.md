**English** · [Bahasa Indonesia](id/jenkins.md)

# Jenkins CI/CD fallback

The root [`Jenkinsfile`](../Jenkinsfile) provides a second CI/CD path when
GitHub Actions is unavailable or its hosted-runner allowance is exhausted. It
does not provision Jenkins itself. A controller, three native agents, tools,
credentials, and a repository webhook must still be configured by an
administrator.

The pipeline deliberately keeps publishing manual. A normal branch or pull
request build runs tests on Windows, Linux, and macOS with Python 3.10 and 3.13,
but does not create desktop packages or a GitHub Release.

## Jenkins components

Use a current Jenkins LTS installation with these components:

- Pipeline and Pipeline: Declarative;
- Git;
- Credentials Binding;
- GitHub Branch Source for a Multibranch Pipeline;
- an external Artifact Manager, strongly recommended for the large native
  package stashes.

The Jenkins documentation describes the
[Multibranch Pipeline](https://www.jenkins.io/doc/book/pipeline/multibranch/)
and [Declarative Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/).
Create a Multibranch Pipeline for
`git@github.com:dirhamtriyadi/spade65-non-qmk.git`, keep the script path as
`Jenkinsfile`, and configure the GitHub webhook normally used by the Branch
Source plugin.

Do not allow an untrusted pull request to replace a `Jenkinsfile` that can use
controller credentials. Apply Jenkins' trusted-revision or trusted-author
policy before enabling pull-request discovery; see
[Securing multibranch pipelines](https://www.jenkins.io/doc/book/security/securing-org-folders-and-multibranch-pipelines/).
The pipeline also refuses release publication from a pull-request job or from
a multibranch job other than `main`, but that runtime check is not a substitute
for Jenkins permission and trust configuration.

## Native agents

Attach these exact labels to agents. Every agent needs Git, Node.js, outbound
HTTPS access to GitHub and PyPI, and enough disk space for isolated virtual
environments and desktop bundles.

| Label | Required host and commands |
|---|---|
| `linux` | Ubuntu 22.04 x86_64; `python3.10`, `python3.13`, Bash, `curl`, `sha256sum`, `dpkg-query`; GitHub CLI `gh` for release jobs |
| `windows` | Windows x64; Python Launcher commands `py -3.10` and `py -3.13`, PowerShell, Node.js, and Microsoft Edge WebView2 Runtime |
| `macos` | macOS with Xcode Command Line Tools; `python3.10`, `python3.13`, `lipo`, `codesign`, `hdiutil`, and a Python.org universal2 Python 3.13 interpreter |

The Linux packaging stage enforces the same Ubuntu 22.04 x86_64 baseline as
GitHub Actions. Preinstall its runtime packages:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends --yes \
  libstdc++6 libgcc-s1 libgbm1 libfontconfig1 libfreetype6 \
  libexpat1 libx11-6 libx11-xcb1 libasound2 libegl1 libgl1 \
  libxcb-shape0 libxcb-image0 libxcb-xkb1 libxcb-icccm4 \
  libxkbcommon-x11-0 libxcb-util1 libxcb-cursor0 libxcb-keysyms1 \
  libxcb-render-util0 curl coreutils
```

The macOS package stage defaults to the universal2 interpreter at:

```text
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13
```

Install and verify the pinned Python.org interpreter once while preparing the
agent, using [`packaging/prepare_macos_ci.sh`](../packaging/prepare_macos_ci.sh)
as the reference. If the interpreter is elsewhere, define
`SPADE65_MACOS_PYTHON` in that node's environment. A thin Homebrew or
single-architecture interpreter is rejected because every Mach-O payload in
the release must contain both `x86_64` and `arm64` slices.

## Release credential

Create one Jenkins **Secret text** credential with ID:

```text
spade65-github-token
```

Use a fine-grained GitHub token limited to this repository with the minimum
permission needed to create and edit Releases (`Contents: Read and write`). The
credential is requested only by the two opt-in release stages; ordinary CI and
package-preflight stages do not receive it. The `linux` agent used for those
stages must have an authenticated-compatible `gh` executable, but must not have
a separately persisted maintainer login.

## Pipeline parameters

| Parameter | Default | Effect |
|---|---:|---|
| `BUILD_DESKTOP` | `false` | Builds, smoke-tests, and archives all three native packages |
| `RELEASE_TAG` | empty | Selects an existing exact `vMAJOR.MINOR.PATCH` tag and builds its immutable commit |
| `PUBLISH_RELEASE` | `false` | Implies all native builds and publishes the selected tag after verification |

Common runs are:

- automatic branch/PR CI: leave every parameter at its default;
- package preflight: set `BUILD_DESKTOP=true`;
- test an existing tag without publishing: set only `RELEASE_TAG`;
- release from the `main` job: set `RELEASE_TAG=vX.Y.Z` and
  `PUBLISH_RELEASE=true`. `BUILD_DESKTOP` may remain false because publication
  enables the package stages automatically.

On the first scan Jenkins may need one initial build to register parameters;
subsequent runs appear as **Build with Parameters**.

## Publication guarantees

For an opt-in release, the pipeline:

1. validates the tag format and matches it against `pyproject.toml` and
   `spade65/__init__.py`;
2. resolves the annotated or lightweight tag to one commit and makes every
   agent build that exact commit;
3. refuses an already-published GitHub Release before expensive builds start;
4. runs the six test cells and three native package builds;
5. verifies and archives exactly the Windows ZIP, Linux AppImage, and universal
   macOS DMG;
6. fetches the tag again and aborts if it moved;
7. creates or reuses only a draft Release, rejects unexpected assets, uploads
   the three expected assets, verifies their count, and then publishes it.

The job uses `disableConcurrentBuilds()` so two publications cannot overlap in
the `main` job. Never move a published tag. If released source must change,
publish a new patch version, as described in the
[desktop release guide](releasing.md).

## Artifact storage and retention

Native files move between agents through `stash`/`unstash`, then Jenkins keeps
them with `archiveArtifacts`. The pipeline retains 20 build records but only
the latest three sets of archived packages. This policy applies to Jenkins
artifacts only and never deletes GitHub Release assets.

These packages, particularly the AppImage, are large. Jenkins warns that large
stashes can consume substantial controller CPU and network bandwidth. Configure
an external Artifact Manager such as the
[Artifact Manager on S3 plugin](https://plugins.jenkins.io/artifact-manager-s3/)
before using native builds regularly. See the Jenkins
[`stash` step documentation](https://www.jenkins.io/doc/pipeline/steps/workflow-basic-steps/#stash-stash-some-files-to-be-used-later-in-the-build)
for that storage behavior.

Jenkins validates the Declarative Pipeline against the plugins installed on
the actual controller. After setup, run default CI first, then a package
preflight, before granting the release credential or relying on this pipeline
for production publication.
