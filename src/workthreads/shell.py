from __future__ import annotations


SUPPORTED_SHELLS = {"bash", "zsh", "fish"}


def completion_script(shell: str) -> str:
    ensure_supported(shell)
    if shell == "fish":
        return FISH_COMPLETION
    if shell == "zsh":
        return ZSH_COMPLETION
    return BASH_COMPLETION


def init_script(shell: str) -> str:
    ensure_supported(shell)
    if shell == "fish":
        return FISH_INIT
    if shell == "zsh":
        return ZSH_COMPLETION + "\n" + ZSH_INIT
    return BASH_COMPLETION + "\n" + BASH_INIT


def ensure_supported(shell: str) -> None:
    if shell not in SUPPORTED_SHELLS:
        supported = ", ".join(sorted(SUPPORTED_SHELLS))
        from .errors import UsageError

        raise UsageError(f"unsupported shell: {shell}", hint=f"expected one of: {supported}")


BASH_COMPLETION = r'''# wt bash completion
_wt_completion() {
  local cur prev commands
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  commands="add new create delete rm list ls config hooks completion init root current"
  case "$prev" in
    completion|init)
      COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") )
      return 0
      ;;
    hooks)
      COMPREPLY=( $(compgen -W "dir init path edit" -- "$cur") )
      return 0
      ;;
    path|edit)
      COMPREPLY=( $(compgen -W "post-create pre-delete" -- "$cur") )
      return 0
      ;;
  esac
  if [[ "$COMP_CWORD" == 1 ]]; then
    COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
    return 0
  fi
  COMPREPLY=( $(compgen -W "--path --worktrees-dir --base --fetch --no-fetch --copy-local --copy-ignored --copy-untracked --overwrite --skip-hooks --cleanup-on-failure --post-create --pre-delete --force --delete-branch --keep-branch --cd --no-cd" -- "$cur") )
}
complete -F _wt_completion wt
'''


ZSH_COMPLETION = r'''#compdef wt
_wt() {
  local -a commands flags shells
  commands=(add new create delete rm list ls config hooks completion init root current)
  flags=(--path --worktrees-dir --base --fetch --no-fetch --copy-local --copy-ignored --copy-untracked --overwrite --skip-hooks --cleanup-on-failure --post-create --pre-delete --force --delete-branch --keep-branch --cd --no-cd)
  shells=(bash zsh fish)
  if (( CURRENT == 2 )); then
    _describe 'command' commands
  elif [[ ${words[2]} == hooks && CURRENT == 3 ]]; then
    local -a hook_commands=(dir init path edit)
    _describe 'hook command' hook_commands
  elif [[ ${words[2]} == hooks && (${words[3]} == path || ${words[3]} == edit) ]]; then
    local -a hook_names=(post-create pre-delete)
    _describe 'hook' hook_names
  elif [[ ${words[2]} == completion || ${words[2]} == init ]]; then
    _describe 'shell' shells
  else
    _describe 'flag' flags
  fi
}
if (( $+functions[compdef] )); then
  compdef _wt wt
fi
'''


FISH_COMPLETION = r'''# wt fish completion
complete -c wt -f -n "__fish_use_subcommand" -a "add new create delete rm list ls config hooks completion init root current"
complete -c wt -f -n "__fish_seen_subcommand_from hooks" -a "dir init path edit"
complete -c wt -f -n "__fish_seen_subcommand_from hooks; and contains -- (commandline -opc)[3] path edit" -a "post-create pre-delete"
complete -c wt -f -n "__fish_seen_subcommand_from completion init" -a "bash zsh fish"
complete -c wt -l path -r
complete -c wt -l worktrees-dir -r
complete -c wt -l base -r
complete -c wt -l fetch
complete -c wt -l no-fetch
complete -c wt -l copy-local
complete -c wt -l copy-ignored
complete -c wt -l copy-untracked
complete -c wt -l overwrite
complete -c wt -l skip-hooks
complete -c wt -l cleanup-on-failure
complete -c wt -l post-create -r
complete -c wt -l pre-delete -r
complete -c wt -l force
complete -c wt -l delete-branch
complete -c wt -l keep-branch
complete -c wt -l cd
complete -c wt -l no-cd
'''


BASH_INIT = r'''# wt bash integration
__wt_bin="${WT_BIN:-$(command -v wt)}"
__wt_should_cd() {
  case "$1" in
    add|new|create)
      case " $* " in *" --no-cd "*) return 1;; esac
      case " $* " in *" --cd "*) return 0;; esac
      [ "$("$__wt_bin" config get shell.cdAfterAdd 2>/dev/null)" = "true" ]
      ;;
    delete|rm)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}
wt() {
  local tmp wt_status last
  if __wt_should_cd "$@"; then
    tmp="$(mktemp)"
    WT_SHELL_INTEGRATION=1 WT_CD_FILE="$tmp" "$__wt_bin" "$@"
    wt_status="$?"
    if [ "$wt_status" -eq 0 ]; then
      last="$(cat "$tmp")"
      [ -d "$last" ] && cd "$last"
    fi
    rm -f "$tmp"
    return "$wt_status"
  fi
  WT_SHELL_INTEGRATION=1 "$__wt_bin" "$@"
}
'''


ZSH_INIT = r'''# wt zsh integration
__wt_bin="${WT_BIN:-$(command -v wt)}"
__wt_should_cd() {
  case "$1" in
    add|new|create)
      case " $* " in *" --no-cd "*) return 1;; esac
      case " $* " in *" --cd "*) return 0;; esac
      [ "$("$__wt_bin" config get shell.cdAfterAdd 2>/dev/null)" = "true" ]
      ;;
    delete|rm)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}
wt() {
  local tmp wt_status last
  if __wt_should_cd "$@"; then
    tmp="$(mktemp)"
    WT_SHELL_INTEGRATION=1 WT_CD_FILE="$tmp" "$__wt_bin" "$@"
    wt_status="$?"
    if [ "$wt_status" -eq 0 ]; then
      last="$(cat "$tmp")"
      [ -d "$last" ] && cd "$last"
    fi
    rm -f "$tmp"
    return "$wt_status"
  fi
  WT_SHELL_INTEGRATION=1 "$__wt_bin" "$@"
}
'''


FISH_INIT = FISH_COMPLETION + r'''
# wt fish integration
set -gx __wt_bin (command -v wt)
function __wt_should_cd
  switch $argv[1]
    case add new create
      contains -- --no-cd $argv; and return 1
      contains -- --cd $argv; and return 0
      test "$($__wt_bin config get shell.cdAfterAdd 2>/dev/null)" = true
    case delete rm
      return 0
    case '*'
      return 1
  end
end
function wt
  if __wt_should_cd $argv
    set -l tmp (mktemp)
    env WT_SHELL_INTEGRATION=1 WT_CD_FILE="$tmp" $__wt_bin $argv
    set -l wt_status $status
    if test "$wt_status" -eq 0
      set -l last (cat $tmp)
      test -d "$last"; and cd "$last"
    end
    rm -f $tmp
    return $wt_status
  end
  env WT_SHELL_INTEGRATION=1 $__wt_bin $argv
end
'''
