# Says when rain is coming in the next two hours, from open-meteo.com's
# forecast in 15-minute steps: rain.py for Windows, with the same output.
# Change both together. RAIN_FORECAST (a saved answer) and RAIN_NOW (Unix
# seconds) stand in for the network and the time now, for the check that
# both scripts agree.

$wet = 0.1
$light = 0.5
$moderate = 2.0
$quietMinutes = 90
$dot = ' ' + [char]0x00B7 + ' '
$plusMinus = [string][char]0x00B1
$words = @{
    Indonesia = @{
        kinds = @('Gerimis', 'Hujan', 'Hujan lebat'); now = '{0} sekarang'; stops = 'Reda sekitar {0}'
        stays = 'Belum reda 2 jam ke depan'; soon = "{0} $plusMinus{1} lagi"; about = 'Sekitar {0}'
        dry = 'Tidak hujan 2 jam ke depan'; offline = 'Prakiraan hujan tidak bisa dimuat'; city = 'Atur kotamu'
        missing = '{0} tidak ditemukan'; hint = 'Nama kota, atau koordinat seperti -6.2,106.8'
    }
    English = @{
        kinds = @('Drizzle', 'Rain', 'Heavy rain'); now = '{0} now'; stops = 'Stops around {0}'
        stays = 'Not stopping in the next 2 hours'; soon = '{0} in about {1}'; about = 'Around {0}'
        dry = 'No rain for 2 hours'; offline = 'Cannot load the rain forecast'; city = 'Set your city'
        missing = '{0} was not found'; hint = 'A city, or coordinates like -6.2,106.8'
    }
}

function Option($key, $default) {
    $value = [Environment]::GetEnvironmentVariable('NOKTA_OPTION_' + $key.ToUpper())
    if ($null -eq $value) { $default } else { $value }
}
function Number($key, $default) {
    $n = 0
    if ([int]::TryParse((Option $key "$default"), [ref]$n)) { $n } else { $default }
}
function DataFile($name) {
    Join-Path $(if ($env:NOKTA_PLUGIN_DATA) { $env:NOKTA_PLUGIN_DATA } else { '.' }) $name
}

# Latitude, longitude and name for "lat,lon" or a city looked up once.
function Place($text) {
    $parts = $text.Split(',')
    if ($parts.Count -eq 2) {
        $lat = 0.0; $lng = 0.0
        $inv = [Globalization.CultureInfo]::InvariantCulture
        if ([double]::TryParse($parts[0].Trim(), 'Float', $inv, [ref]$lat) -and
            [double]::TryParse($parts[1].Trim(), 'Float', $inv, [ref]$lng) -and
            [math]::Abs($lat) -le 90 -and [math]::Abs($lng) -le 180) {
            return @($lat, $lng, ('{0:F2}, {1:F2}' -f $lat, $lng))
        }
    }
    $cache = DataFile 'place.json'
    if (Test-Path $cache) {
        try {
            $saved = Get-Content $cache -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($saved.query -eq $text) { return @([double]$saved.latitude, [double]$saved.longitude, $saved.name) }
        } catch { }
    }
    $url = 'https://geocoding-api.open-meteo.com/v1/search?count=1&format=json&name=' + [Uri]::EscapeDataString($text)
    $found = (Invoke-RestMethod -Uri $url -TimeoutSec 10).results
    if (-not $found) { return $null }
    $hit = @($found)[0]
    $saved = [ordered]@{ query = $text; latitude = $hit.latitude; longitude = $hit.longitude; name = $hit.name }
    try { $saved | ConvertTo-Json -Compress | Set-Content $cache -Encoding UTF8 } catch { }
    @([double]$hit.latitude, [double]$hit.longitude, $hit.name)
}

# [start in Unix seconds, millimetres] for the last 15 minutes and the next two hours.
function Forecast($lat, $lng) {
    if ($env:RAIN_FORECAST) {
        $body = Get-Content $env:RAIN_FORECAST -Raw -Encoding UTF8 | ConvertFrom-Json
    } else {
        $inv = [Globalization.CultureInfo]::InvariantCulture
        $url = 'https://api.open-meteo.com/v1/forecast?minutely_15=precipitation&past_minutely_15=1' +
            '&forecast_minutely_15=9&timeformat=unixtime&latitude=' + $lat.ToString($inv) + '&longitude=' + $lng.ToString($inv)
        $body = Invoke-RestMethod -Uri $url -TimeoutSec 10
    }
    $steps = $body.minutely_15
    for ($i = 0; $i -lt @($steps.time).Count; $i++) {
        $mm = @($steps.precipitation)[$i]
        , @([long]@($steps.time)[$i], $(if ($null -eq $mm) { 0.0 } else { [double]$mm }))
    }
}

function Span($minutes, $english) {
    $h = [math]::Floor($minutes / 60); $m = $minutes % 60
    if ($english) { if ($h) { "$h h $m min" } else { "$m min" } }
    else { if ($h) { "$h jam $m menit" } else { "$m menit" } }
}
function Kind($w, $mm) {
    $w.kinds[$(if ($mm -lt $light) { 0 } elseif ($mm -lt $moderate) { 1 } else { 2 })]
}
function Clock($seconds) {
    [DateTimeOffset]::FromUnixTimeSeconds($seconds).LocalDateTime.ToString('HH:mm')
}
function LastAlert {
    try { [long]((Get-Content (DataFile 'alert.json') -Raw -ErrorAction Stop | ConvertFrom-Json).at) } catch { 0 }
}

function Card($w, $steps, $now, $city) {
    # The step now (the last one started, or the first), and those after it.
    $current = $null
    $ahead = New-Object System.Collections.ArrayList
    foreach ($step in $steps) {
        if ($step[0] -le $now) { $current = $step } else { [void]$ahead.Add($step) }
    }
    if ($null -eq $current -and $steps.Count -gt 0) { $current = $steps[0] }
    $card = [ordered]@{ icon = 'nokta-weather'; tone = 'blue' }
    if ($null -ne $current -and $current[1] -ge $wet) {
        $most = $current[1]
        $dry = $null
        foreach ($step in $ahead) {
            if ($step[1] -lt $wet) { $dry = $step; break }
            $most = [math]::Max($most, $step[1])
        }
        $card.title = $w.now -f (Kind $w $most)
        $card.detail = if ($dry) { $w.stops -f (Clock $dry[0]) } else { $w.stays }
        return @($card, $null)
    }
    $start = -1
    for ($i = 0; $i -lt $ahead.Count; $i++) { if ($ahead[$i][1] -ge $wet) { $start = $i; break } }
    if ($start -lt 0) {
        $card.title = $w.dry; $card.detail = $city; $card.tone = 'gray'
        if ((Option 'show_dry' 'true') -ne 'true') { $card.hidden = $true }
        return @($card, $null)
    }
    $most = 0.0
    for ($i = $start; $i -lt $ahead.Count -and $ahead[$i][1] -ge $wet; $i++) { $most = [math]::Max($most, $ahead[$i][1]) }
    $at = $ahead[$start][0]
    $minutes = [int][math]::Max(1, [math]::Ceiling(($at - $now) / 60))
    $card.title = $w.soon -f (Kind $w $most), (Span $minutes ($w -eq $words.English))
    $card.detail = ($w.about -f (Clock $at)) + $dot + $city
    if ($minutes -gt (Number 'lead_minutes' 30)) { return @($card, $null) }
    if ((Option 'badge' 'true') -eq 'true') {
        $card.badge = if ($minutes -ge 60) { '{0}h{1:D2}' -f [math]::Floor($minutes / 60), ($minutes % 60) } else { "${minutes}m" }
    }
    if ((Option 'alert' 'true') -eq 'true' -and $now - (LastAlert) -ge $quietMinutes * 60) {
        $card.alert = [ordered]@{ id = "rain-$at"; title = $card.title; detail = $card.detail }
        return @($card, $now)
    }
    @($card, $null)
}

[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$w = if ((Option 'language' 'Indonesia') -eq 'English') { $words.English } else { $words.Indonesia }
$text = (Option 'location' 'Jakarta').Trim()
try {
    $found = if ($text) { Place $text } else { $null }
    if (-not $found) {
        $detail = if ($text) { $w.missing -f $text } else { $w.hint }
        @{ title = $w.city; detail = $detail; tone = 'orange' } | ConvertTo-Json -Compress
        exit 0
    }
    $steps = @(Forecast $found[0] $found[1])
} catch {
    @{ title = $w.offline; icon = 'nokta-weather'; tone = 'gray' } | ConvertTo-Json -Compress
    exit 0
}
$now = if ($env:RAIN_NOW) { [long]$env:RAIN_NOW } else { [DateTimeOffset]::Now.ToUnixTimeSeconds() }
$card, $alerted = Card $w $steps $now $found[2]
if ($null -ne $alerted -and -not $env:RAIN_FORECAST) {
    try { @{ at = $alerted } | ConvertTo-Json -Compress | Set-Content (DataFile 'alert.json') } catch { }
}
$card | ConvertTo-Json -Compress -Depth 4
