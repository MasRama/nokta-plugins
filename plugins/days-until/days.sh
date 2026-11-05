#!/bin/sh
# Prints how many days are left until NOKTA_OPTION_DATE. Works with GNU date
# (Linux) and BSD date (macOS).
date_opt=${NOKTA_OPTION_DATE:-2027-01-01}
label=${NOKTA_OPTION_LABEL:-New year}
# Keep the label safe inside JSON: drop quotes and backslashes.
label=$(printf '%s' "$label" | tr -d "\"\\\\")

day_seconds() {
  date -u -d "$1" +%s 2>/dev/null || date -u -j -f '%Y-%m-%d' "$1" +%s 2>/dev/null
}

then_s=$(day_seconds "$date_opt")
if [ -z "$then_s" ]; then
  printf '{"title":"Pick a date","detail":"%s is not a YYYY-MM-DD date","tone":"orange"}\n' "$date_opt"
  exit 0
fi
today_s=$(day_seconds "$(date +%Y-%m-%d)")
days=$(( (then_s - today_s) / 86400 ))

badge=""
if [ "${NOKTA_OPTION_BADGE:-true}" = "true" ] && [ "$days" -ge 0 ]; then
  badge=$(printf '%sd' "$days")
fi
if [ "$days" -gt 1 ]; then
  title="$days days until $label"
elif [ "$days" -eq 1 ]; then
  title="$label is tomorrow"
elif [ "$days" -eq 0 ]; then
  title="$label is today"
elif [ "$days" -eq -1 ]; then
  title="$label was yesterday"
else
  title="$label was $(( -days )) days ago"
fi
alert=""
if [ "$days" -eq 0 ]; then
  alert=$(printf ',"alert":{"id":"today-%s","title":"%s is today"}' "$date_opt" "$label")
fi
printf '{"title":"%s","detail":"%s","tone":"indigo","icon":"nokta-calendar","badge":"%s"%s}\n' \
  "$title" "$date_opt" "$badge" "$alert"
