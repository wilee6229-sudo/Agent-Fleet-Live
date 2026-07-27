export FLEET_DIR="$HOME/fleet"
export PATH="$HOME/.local/bin:$FLEET_DIR:$PATH"
alias fl='fleet'
alias fls='fleet status'
alias flo='fleet logs'
alias flh='fleet hyprland'
export TMUX_TMPDIR=/tmp
PS1='\[\033[01;32m\]agent@\[\033[01;35m\]fleet\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
