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


BASH_COMPLETION = r'''# workthreads wt bash completion
_wt_completion() {
  local cur prev commands
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  commands="add new create delete rm list ls config completion init root current"
  case "$prev" in
    completion|init)
      COMPREPLY=( $(compgen -W "bash zsh fish" -- "$cur") )
      return 0
      ;;
  esac
  if [[ "$COMP_CWORD" == 1 ]]; then
    COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
    return 0
  fi
  COMPREPLY=( $(compgen -W "--path --worktrees-dir --base --fetch --no-fetch --copy-local --copy-ignored --copy-untracked --overwrite --skip-hooks --cleanup-on-failure --post-create --pre-delete --force --delete-branch --keep-branch --cd --no-cd --json" -- "$cur") )
}
complete -F _wt_completion wt
'''


ZSH_COMPLETION = r'''#compdef wt
_wt() {
  local -a commands flags shells
  commands=(add new create delete rm list ls config completion init root current)
  flags=(--path --worktrees-dir --base --fetch --no-fetch --copy-local --copy-ignored --copy-untracked --overwrite --skip-hooks --cleanup-on-failure --post-create --pre-delete --force --delete-branch --keep-branch --cd --no-cd --json)
  shells=(bash zsh fish)
  if (( CURRENT == 2 )); then
    _describe 'command' commands
  elif [[ ${words[2]} == completion || ${words[2]} == init ]]; then
    _describe 'shell' shells
  else
    _describe 'flag' flags
  fi
}
compdef _wt wt
'''


FISH_COMPLETION = r'''# workthreads wt fish completion
complete -c wt -f -n "__fish_use_subcommand" -a "add new create delete rm list ls config completion init root current"
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
complete -c wt -l json
'''


BASH_INIT = r'''# workthreads wt bash integration
__wt_bin="${WT_BIN:-$(command -v wt)}"
__wt_should_cd() {
  case " $* " in *" --no-cd "*) return 1;; esac
  case " $* " in *" --json "*) return 1;; esac
  case "$1" in add|new|create) ;; *) return 1;; esac
  case " $* " in *" --cd "*) return 0;; esac
  [ "$("$__wt_bin" config get shell.cdAfterAdd 2>/dev/null)" = "true" ]
}
wt() {
  local tmp status last
  tmp="$(mktemp)"
  WT_SHELL_INTEGRATION=1 "$__wt_bin" "$@" | tee "$tmp"
  status="${PIPESTATUS[0]}"
  if [ "$status" -eq 0 ] && __wt_should_cd "$@"; then
    last="$(tail -n 1 "$tmp")"
    [ -d "$last" ] && cd "$last"
  fi
  rm -f "$tmp"
  return "$status"
}
'''


ZSH_INIT = r'''# workthreads wt zsh integration
__wt_bin="${WT_BIN:-$(command -v wt)}"
__wt_should_cd() {
  case " $* " in *" --no-cd "*) return 1;; esac
  case " $* " in *" --json "*) return 1;; esac
  case "$1" in add|new|create) ;; *) return 1;; esac
  case " $* " in *" --cd "*) return 0;; esac
  [ "$("$__wt_bin" config get shell.cdAfterAdd 2>/dev/null)" = "true" ]
}
wt() {
  local tmp status last
  tmp="$(mktemp)"
  WT_SHELL_INTEGRATION=1 "$__wt_bin" "$@" | tee "$tmp"
  status="${pipestatus[1]}"
  if [ "$status" -eq 0 ] && __wt_should_cd "$@"; then
    last="$(tail -n 1 "$tmp")"
    [ -d "$last" ] && cd "$last"
  fi
  rm -f "$tmp"
  return "$status"
}
'''


FISH_INIT = FISH_COMPLETION + r'''
# workthreads wt fish integration
set -gx __wt_bin (command -v wt)
function __wt_should_cd
  contains -- --no-cd $argv; and return 1
  contains -- --json $argv; and return 1
  contains -- $argv[1] add new create; or return 1
  contains -- --cd $argv; and return 0
  test "$($__wt_bin config get shell.cdAfterAdd 2>/dev/null)" = true
end
function wt
  set -l tmp (mktemp)
  env WT_SHELL_INTEGRATION=1 $__wt_bin $argv | tee $tmp
  set -l status $pipestatus[1]
  if test "$status" -eq 0; and __wt_should_cd $argv
    set -l last (tail -n 1 $tmp)
    test -d "$last"; and cd "$last"
  end
  rm -f $tmp
  return $status
end
'''
