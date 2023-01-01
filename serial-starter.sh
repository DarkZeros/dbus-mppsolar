#! /bin/bash
exec 2>&1

. $(dirname $0)/functions.sh

BASE_DIR='/opt/victronenergy'
CACHE_DIR='/data/var/lib/serial-starter'
SERVICE_DIR='/var/volatile/services'
SS_CONFIG='/etc/venus/serial-starter.conf'

# Remove stale service symlinks
find -L /service -maxdepth 1 -type l -delete

mkdir -p "$CACHE_DIR"
mkdir -p "$SERVICE_DIR"

get_property() {
    udevadm info --query=property --name="$1" | sed -n "s/^$2=//p"
}

get_product() {
    tty=$1
    dev=/sys/class/tty/$tty/device

    if [ ! -L $dev ]; then
        # no device, probably a virtual terminal
        echo ignore
        return
    fi

    ve_product=$(get_property $tty VE_PRODUCT)

    if [ -n "$ve_product" ]; then
        echo $ve_product
        return
    fi

    subsys=$(basename $(readlink $dev/subsystem))

    case $subsys in
        usb*)
            get_property $tty ID_MODEL
            ;;
        *)
            echo ignore
            ;;
    esac
}

get_program() {
    tty=$1
    product=$2

    ve_service=$(get_property $tty VE_SERVICE)

    if [ -n "$ve_service" ]; then
        # If a seperate debug console is lacking a ve-direct port can be used instead..
        if [ "$ve_service" = "vedirect-or-vegetty" ]; then
            if [ -e /service/vegetty ]; then
                echo ignore
            else
                echo vedirect
            fi
            return
        fi

        echo $ve_service
        return
    fi

    case $product in
        builtin-mkx)
            echo mkx
            ;;
        builtin-vedirect)
            echo vedirect
            ;;
        ignore)
            echo ignore
            ;;
        *)
            echo default
            ;;
    esac
}

create_service() {
    service=$1
    tty=$2

    # check if service already exists
    test -d "/service/$SERVICE" && return 0

    tmpl=$BASE_DIR/service-templates/$service

    # check existence of service template
    if [ ! -d "$tmpl" ]; then
        echo "ERROR: no service template for $service"
        return 1
    fi

    echo "INFO: Create daemontools service $SERVICE"

    # copy service
    cp -a "$tmpl" "$SERVICE_DIR/$SERVICE"

    # Patch run files for tty device
    sed -i "s:TTY:$TTY:" "$SERVICE_DIR/$SERVICE/run"
    sed -i "s:TTY:$TTY:" "$SERVICE_DIR/$SERVICE/log/run"

    # Create symlink to /service
    ln -sf "$SERVICE_DIR/$SERVICE" "/service/$SERVICE"

    # wait for svscan to find service
    sleep 6
}

start_service() {
    eval service="\$svc_$1"
    tty=$2

    if [ -z "$service" ]; then
        echo "ERROR: unknown service $1"
        return 1
    fi

    SERVICE="$service.$tty"

    if ! create_service $service $tty; then
        unlock_tty $tty
        return 1
    fi

    # update product string
    sed -i "s:PRODUCT\(=[^ ]*\)*:PRODUCT=$PRODUCT:" "$SERVICE_DIR/$SERVICE/run"

    svc -u "/service/$SERVICE/log"

    if [ $AUTOPROG = n ]; then
        echo "INFO: Start service $SERVICE"
        svc -u "/service/$SERVICE"
    else
        echo "INFO: Start service $SERVICE once"
        svc -o "/service/$SERVICE"
    fi
}

# recursively expand aliases, removing duplicates
expand_alias() {
    set -- $(echo $1 | tr : ' ')

    for v; do
        eval x="\$exp_$v"
        test -n "$x" && continue

        eval e="\$alias_$v"
        eval "exp_$v=1"

        if [ -n "$e" ]; then
            expand_alias "$e"
        else
            echo $v
        fi
    done
}

# expand aliases and return colon separated list
get_alias() (
    set -- $(expand_alias $1)
    IFS=:
    echo "$*"
)

check_val() {
    if echo "$1" | grep -Eqv "^$2+\$"; then
        echo "ERROR: $3 ${1:+'$1'}" >&2
    fi
}

load_config() {
    cfg=$1

    test -r "$cfg" || return

    echo "INFO: loading config file $cfg" >&2

    sed 's/#.*//' "$cfg" | while read keyword name value; do
        # ignore blank lines
        test -z "$keyword" && continue

        case $keyword in
            service)
                check_val "$name" '[[:alnum:]_]' 'invalid service name'
                check_val "$value" '[[:alnum:]_:.-]' 'invalid service value'
                echo "svc_$name=$value"
                ;;
            alias)
                check_val "$name" '[[:alnum:]_]' 'invalid alias name'
                check_val "$value" '[[:alnum:]_:-]' 'invalid alias value'
                echo "alias_$name=$value"
                ;;
            include)
                check_val "$name" . 'include: name required'
                if [ -d "$name" ]; then
                    for file in "$name"/*.conf; do
                        load_config "$file"
                    done
                else
                    load_config "$name"
                fi
                ;;
            *)
                echo "ERROR: unknown keyword $keyword" >&2
                ;;
        esac
    done
}

echo "serstart starting"

eval $(load_config "$SS_CONFIG")

while true; do
    TTYS=$(ls /dev/serial-starter/ 2>/dev/null)
    for TTY in $TTYS; do
        CACHE_FILE="$CACHE_DIR/$TTY"
        PROG_FILE="/tmp/$TTY.prog"

        lock_tty $TTY || continue

        # device may have vanished while running for loop
        if ! test -e /dev/serial-starter/$TTY; then
            unlock_tty $TTY
            continue
        fi

        # check for a known device
        PRODUCT=$(get_product $TTY)
        PROGRAMS=$(get_program $TTY $PRODUCT)
        PROGRAMS=$(get_alias $PROGRAMS)

        if [ "$PROGRAMS" = ignore ]; then
            rm /dev/serial-starter/$TTY
            unlock_tty $TTY
            continue
        elif [ "${PROGRAMS%%:*}" = "${PROGRAMS}" ]; then
            AUTOPROG=n
            PROGRAM=$PROGRAMS
            rm /dev/serial-starter/$TTY
        else
            AUTOPROG=y

            if [ -f "$PROG_FILE" ]; then
                # next entry in probe cycle
                PROGRAM=$(cat $PROG_FILE)
            elif [ -f "$CACHE_FILE" ]; then
                # last used program
                PROGRAM=$(cat $CACHE_FILE)
            fi

            if ! echo ":$PROGRAMS:" | grep -q ":$PROGRAM:"; then
                # invalid cache, reset
                PROGRAM=${PROGRAMS%%:*}
            fi
        fi

        for n in $(echo $PROGRAMS | tr : ' '); do
            mkdir -p /run/serial-starter/$n
            ln -sf /dev/$TTY /run/serial-starter/$n/$TTY
        done

        echo "$PROGRAM" >"$CACHE_FILE"

        start_service $PROGRAM $TTY &

        if [ $AUTOPROG = y ]; then
            NEXT=${PROGRAMS#*${PROGRAM}:}
            NEXT=${NEXT%%:*}
            echo "$NEXT" >"$PROG_FILE"
        fi

        sleep 1
    done

    sleep 2
done
