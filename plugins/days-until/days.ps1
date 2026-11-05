# Prints how many days are left until NOKTA_OPTION_DATE.
$dateText = if ($env:NOKTA_OPTION_DATE) { $env:NOKTA_OPTION_DATE } else { '2027-01-01' }
$label = if ($env:NOKTA_OPTION_LABEL) { $env:NOKTA_OPTION_LABEL } else { 'New year' }
$then = [datetime]::MinValue
if (-not [datetime]::TryParseExact($dateText, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture, 'None', [ref]$then)) {
    @{ title = 'Pick a date'; detail = "$dateText is not a YYYY-MM-DD date"; tone = 'orange' } | ConvertTo-Json -Compress
    exit 0
}
$days = [int]($then.Date - (Get-Date).Date).TotalDays
$title = if ($days -gt 1) { "$days days until $label" }
    elseif ($days -eq 1) { "$label is tomorrow" }
    elseif ($days -eq 0) { "$label is today" }
    elseif ($days -eq -1) { "$label was yesterday" }
    else { "$label was $(-$days) days ago" }
$card = @{ title = $title; detail = $dateText; tone = 'indigo'; icon = 'nokta-calendar' }
if ($env:NOKTA_OPTION_BADGE -ne 'false' -and $days -ge 0) { $card.badge = "${days}d" }
if ($days -eq 0) { $card.alert = @{ id = "today-$dateText"; title = "$label is today" } }
$card | ConvertTo-Json -Compress -Depth 3
