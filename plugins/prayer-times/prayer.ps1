# The five daily prayer times, worked out on this computer from where you are:
# prayer.py for Windows, with the same method and output. Change both together.
# PRAYER_NOW (yyyy-MM-ddTHH:mm) stands in for the time now, for the check
# that both scripts agree.

$methods = [ordered]@{
    'Kemenag (Indonesia)'  = @(20.0, 18.0, 0, 2)
    'JAKIM (Malaysia)'     = @(20.0, 18.0, 0, 0)
    'Muslim World League'  = @(18.0, 17.0, 0, 0)
    'Umm al-Qura (Makkah)' = @(18.5, 0, 90, 0)
    'Egypt'                = @(19.5, 17.5, 0, 0)
    'ISNA (North America)' = @(15.0, 15.0, 0, 0)
}
$defaultMethod = 'Kemenag (Indonesia)'
$lateMinutes = 10
$dot = ' ' + [char]0x00B7 + ' '

function Option($key, $default) {
    $value = [Environment]::GetEnvironmentVariable('NOKTA_OPTION_' + $key.ToUpper())
    if ($null -eq $value) { $default } else { $value }
}
function Number($key, $default) {
    $n = 0
    if ([int]::TryParse((Option $key "$default"), [ref]$n)) { $n } else { $default }
}
function Fix($a, $b) { $r = $a % $b; if ($r -lt 0) { $r + $b } else { $r } }
function Rad($d) { $d * [math]::PI / 180 }
function Deg($r) { $r * 180 / [math]::PI }
function DSin($d) { [math]::Sin((Rad $d)) }
function DCos($d) { [math]::Cos((Rad $d)) }
function DTan($d) { [math]::Tan((Rad $d)) }

# The sun's declination and the equation of time (hours) on Julian day $jd.
function Sun($jd) {
    $d = $jd - 2451545.0
    $g = Fix (357.529 + 0.98560028 * $d) 360
    $q = Fix (280.459 + 0.98564736 * $d) 360
    $ecl = Fix ($q + 1.915 * (DSin $g) + 0.020 * (DSin (2 * $g))) 360
    $e = 23.439 - 0.00000036 * $d
    $ra = Fix ((Deg ([math]::Atan2((DCos $e) * (DSin $ecl), (DCos $ecl)))) / 15) 24
    @((Deg ([math]::Asin((DSin $e) * (DSin $ecl)))), ($q / 15 - $ra))
}

function Julian([datetime]$day) {
    $y = $day.Year; $m = $day.Month
    if ($m -le 2) { $y -= 1; $m += 12 }
    $a = [math]::Floor($y / 100)
    $b = 2 - $a + [math]::Floor($a / 4)
    [math]::Floor(365.25 * ($y + 4716)) + [math]::Floor(30.6001 * ($m + 1)) + $day.Day + $b - 1524.5
}

# The five times on $day as this computer's local times, to the minute.
function Moments([datetime]$day, $lat, $lng, $method, $hanafi) {
    $fajrAngle, $ishaAngle, $ishaMinutes, $extra = $methods[$method]
    $jd = (Julian $day) - $lng / 360
    $noon = { param($hour) Fix (12 - (Sun ($jd + $hour / 24))[1]) 24 }
    $angleTime = {
        param($angle, $hour, $beforeNoon)
        $decl = (Sun ($jd + $hour / 24))[0]
        $cosT = (-(DSin $angle) - (DSin $decl) * (DSin $lat)) / ((DCos $decl) * (DCos $lat))
        $t = (Deg ([math]::Acos([math]::Max(-1.0, [math]::Min(1.0, $cosT))))) / 15
        $n = & $noon $hour
        if ($beforeNoon) { $n - $t } else { $n + $t }
    }
    $decl = (Sun ($jd + 13 / 24))[0]
    $factor = if ($hanafi) { 2 } else { 1 }
    $asrAngle = -(Deg ([math]::Atan(1 / ($factor + (DTan ([math]::Abs($lat - $decl)))))))
    $fajr = & $angleTime $fajrAngle 5 $true
    $dhuhr = & $noon 12
    $asr = & $angleTime $asrAngle 13 $false
    $maghrib = & $angleTime 0.833 18 $false
    $isha = if ($ishaMinutes) { $maghrib + $ishaMinutes / 60 } else { & $angleTime $ishaAngle 18 $false }
    $midnight = [datetime]::SpecifyKind($day.Date, 'Utc')
    foreach ($hours in @($fajr, $dhuhr, $asr, $maghrib, $isha)) {
        $minutes = [math]::Round(($hours - $lng / 15 + $extra / 60) * 60)
        $midnight.AddMinutes($minutes).ToLocalTime()
    }
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
    $data = if ($env:NOKTA_PLUGIN_DATA) { $env:NOKTA_PLUGIN_DATA } else { '.' }
    $cache = Join-Path $data 'place.json'
    if (Test-Path $cache) {
        try {
            $saved = Get-Content $cache -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($saved.query -eq $text) { return @([double]$saved.latitude, [double]$saved.longitude, $saved.name) }
        } catch { }
    }
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $url = 'https://geocoding-api.open-meteo.com/v1/search?count=1&format=json&name=' + [Uri]::EscapeDataString($text)
    $found = (Invoke-RestMethod -Uri $url -TimeoutSec 10).results
    if (-not $found) { return $null }
    $hit = @($found)[0]
    $saved = [ordered]@{ query = $text; latitude = $hit.latitude; longitude = $hit.longitude; name = $hit.name }
    try { $saved | ConvertTo-Json -Compress | Set-Content $cache -Encoding UTF8 } catch { }
    @([double]$hit.latitude, [double]$hit.longitude, $hit.name)
}

function Until($minutes, $english) {
    $h = [math]::Floor($minutes / 60); $m = $minutes % 60
    if ($english) { if ($h) { "in $h h $m min" } else { "in $m min" } }
    else { if ($h) { "$h jam $m menit lagi" } else { "$m menit lagi" } }
}

function Card([datetime]$now, $lat, $lng, $city) {
    $english = (Option 'language' 'Indonesia') -eq 'English'
    $names = if ($english) { @('Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha') } else { @('Subuh', 'Dzuhur', 'Ashar', 'Maghrib', 'Isya') }
    $method = Option 'method' $defaultMethod
    if (-not $methods.Contains($method)) { $method = $defaultMethod }
    $hanafi = (Option 'asr' "Shafi'i") -eq 'Hanafi'
    $today = @(Moments $now.Date $lat $lng $method $hanafi)
    $tomorrow = @(Moments $now.Date.AddDays(1) $lat $lng $method $hanafi)
    $name = $names[0]; $at = $tomorrow[0]
    for ($i = 0; $i -lt 5; $i++) {
        if ($today[$i] -gt $now) { $name = $names[$i]; $at = $today[$i]; break }
    }
    $left = [int][math]::Ceiling(($at - $now).TotalMinutes)
    $clock = $at.ToString('HH:mm')
    $card = [ordered]@{
        title  = "$name $clock$dot$(Until $left $english)"
        detail = (0..4 | ForEach-Object { '{0} {1}' -f $names[$_], $today[$_].ToString('HH:mm') }) -join $dot
        icon   = 'nokta-alarm'
        tone   = 'teal'
        items  = @(0..4 | ForEach-Object { [ordered]@{ title = $names[$_]; detail = $today[$_].ToString('HH:mm') } })
    }
    $badgeMinutes = Number 'badge_minutes' 30
    if ($left -gt 0 -and $left -le $badgeMinutes) {
        $card.badge = if ($left -ge 60) { '{0}h{1:D2}' -f [math]::Floor($left / 60), ($left % 60) } else { "${left}m" }
    }
    if ((Option 'alert' 'true') -eq 'true') {
        for ($i = 0; $i -lt 5; $i++) {
            $late = ($now - $today[$i]).TotalMinutes
            if ($late -ge 0 -and $late -lt $lateMinutes) {
                $title = if ($english) { "Time for $($names[$i])" } else { "Waktunya $($names[$i])" }
                $card.alert = [ordered]@{ id = "$($today[$i].ToString('yyyy-MM-dd'))-$($names[$i])"; title = $title; detail = "$($today[$i].ToString('HH:mm'))$dot$city" }
            }
        }
    }
    $remind = Number 'remind_minutes' 0
    if (-not $card.Contains('alert') -and $remind -gt 0 -and $left -le $remind) {
        $card.alert = [ordered]@{ id = "$($at.ToString('yyyy-MM-dd'))-$name-soon"; title = "$name $(Until $left $english)"; detail = "$clock$dot$city" }
    }
    $card
}

$text = (Option 'location' 'Jakarta').Trim()
$english = (Option 'language' 'Indonesia') -eq 'English'
try {
    $found = if ($text) { Place $text } else { $null }
} catch {
    $card = if ($english) { @{ title = 'Cannot look up the city'; detail = 'No connection; or set coordinates like -6.2,106.8'; tone = 'orange' } }
        else { @{ title = 'Kota tidak bisa dicari'; detail = 'Tidak ada koneksi; atau isi koordinat seperti -6.2,106.8'; tone = 'orange' } }
    $card | ConvertTo-Json -Compress
    exit 0
}
if (-not $found) {
    $detail = if ($text) { if ($english) { "$text was not found" } else { "$text tidak ditemukan" } }
        elseif ($english) { 'A city, or coordinates like -6.2,106.8' } else { 'Nama kota, atau koordinat seperti -6.2,106.8' }
    @{ title = $(if ($english) { 'Set your city' } else { 'Atur kotamu' }); detail = $detail; tone = 'orange' } | ConvertTo-Json -Compress
    exit 0
}
$now = if ($env:PRAYER_NOW) {
    [datetime]::ParseExact($env:PRAYER_NOW, "yyyy-MM-dd'T'HH:mm", [Globalization.CultureInfo]::InvariantCulture)
} else { $n = Get-Date; $n.Date.AddHours($n.Hour).AddMinutes($n.Minute) }
Card $now $found[0] $found[1] $found[2] | ConvertTo-Json -Compress -Depth 4
