# `repo-research`

**Usage**:

```console
$ repo-research [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `diagnostics`: Diagnose issues with the setup
* `pulse`: Analyze activity of user&#x27;s starred...
* `topics`: Search for repositories related to...
* `hotspots`: Analyze maintenance hotspots in a repository
* `history`: List recent conversation history
* `show`: Display full conversation transcript
* `chat`: Start a new interactive chat session
* `resume`: Resume an existing conversation interactively
* `ui`: Launch the Gradio web UI

## `repo-research diagnostics`

Diagnose issues with the setup

**Usage**:

```console
$ repo-research diagnostics [OPTIONS]
```

**Options**:

* `--model-name TEXT`: Override the model name for this command
* `--thread-id TEXT`: Resume conversation with this thread ID
* `--help`: Show this message and exit.

## `repo-research pulse`

Analyze activity of user&#x27;s starred repositories

**Usage**:

```console
$ repo-research pulse [OPTIONS]
```

**Options**:

* `-s, --sort [created|updated]`: Sort starred repositories by: created or updated  [default: updated]
* `-d, --direction [asc|desc]`: Sort direction: asc or desc  [default: desc]
* `-l, --limit INTEGER RANGE`: Maximum number of starred repositories to analyze (1-100)  [default: 50; 1&lt;=x&lt;=100]
* `--model-name TEXT`: Override the model name for this command
* `--thread-id TEXT`: Resume conversation with this thread ID
* `--help`: Show this message and exit.

## `repo-research topics`

Search for repositories related to specific topics/with specific labels

**Usage**:

```console
$ repo-research topics [OPTIONS] TOPICS_RAW
```

**Arguments**:

* `TOPICS_RAW`: [required]

**Options**:

* `-s, --sort [created|updated]`: Sort results by: stars, forks, or updated  [default: updated]
* `-l, --limit INTEGER RANGE`: Maximum number of results to return (1-100)  [default: 25; 1&lt;=x&lt;=100]
* `--language TEXT`: Filter by programming language (e.g., &#x27;python&#x27;, &#x27;rust&#x27;)
* `--license TEXT`: Filter by license type (e.g., &#x27;mit&#x27;, &#x27;apache-2.0&#x27;, &#x27;gpl-3.0&#x27;)
* `--min-stars INTEGER RANGE`: Minimum number of stars  [default: 25; x&gt;=0]
* `--max-stars INTEGER RANGE`: Maximum number of stars  [x&gt;=0]
* `-d, --pushed-within-days INTEGER RANGE`: Only repos pushed within last N days (1-365)  [1&lt;=x&lt;=365]
* `--archived`: Filter by archived status (true=only archived, false=exclude archived)
* `--fork`: Filter by fork status (true=only forks, false=exclude forks)
* `--model-name TEXT`: Override the model name for this command
* `--thread-id TEXT`: Resume conversation with this thread ID
* `--help`: Show this message and exit.

## `repo-research hotspots`

Analyze maintenance hotspots in a repository

**Usage**:

```console
$ repo-research hotspots [OPTIONS] REPO
```

**Arguments**:

* `REPO`: [required]

**Options**:

* `-d, --days INTEGER RANGE`: Number of days of history to analyze (1-365)  [default: 90; 1&lt;=x&lt;=365]
* `-c, --max-commits INTEGER RANGE`: Maximum number of commits to analyze (1-1000)  [default: 200; 1&lt;=x&lt;=1000]
* `-m, --min-changes INTEGER RANGE`: Minimum changes required for a file to be a hotspot (≥1)  [default: 3; x&gt;=1]
* `-p, --path TEXT`: Focus analysis on specific path (e.g., &#x27;src/integrations&#x27;)
* `--model-name TEXT`: Override the model name for this command
* `--thread-id TEXT`: Resume conversation with this thread ID
* `--export-md`: Export analysis to markdown file in ./outputs/ directory
* `--help`: Show this message and exit.

## `repo-research history`

List recent conversation history

**Usage**:

```console
$ repo-research history [OPTIONS]
```

**Options**:

* `-n, --limit INTEGER`: Number of conversations to show  [default: 20]
* `--help`: Show this message and exit.

## `repo-research show`

Display full conversation transcript

**Usage**:

```console
$ repo-research show [OPTIONS] THREAD_ID
```

**Arguments**:

* `THREAD_ID`: [required]

**Options**:

* `--help`: Show this message and exit.

## `repo-research chat`

Start a new interactive chat session

**Usage**:

```console
$ repo-research chat [OPTIONS]
```

**Options**:

* `--model-name TEXT`: Override the model name for this command
* `--help`: Show this message and exit.

## `repo-research resume`

Resume an existing conversation interactively

**Usage**:

```console
$ repo-research resume [OPTIONS] [THREAD_ID]
```

**Arguments**:

* `[THREAD_ID]`: Thread ID to resume (omit to use --last)

**Options**:

* `--last`: Resume the most recent conversation
* `--model-name TEXT`: Override the model name for this command
* `--help`: Show this message and exit.

## `repo-research ui`

Launch the Gradio web UI

**Usage**:

```console
$ repo-research ui [OPTIONS]
```

**Options**:

* `--share`: Create a public share link
* `--host TEXT`: Server hostname/IP address  [default: 127.0.0.1]
* `--port INTEGER`: Server port number  [default: 7860]
* `--help`: Show this message and exit.
