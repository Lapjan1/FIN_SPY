$ff = 'C:\Users\dshan\AppData\Local\Programs\Python\Python314-arm64\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-aarch64-v9.0.1.exe'
$cap = Join-Path $env:USERPROFILE 'Videos\Captures'
$out = Join-Path $env:TEMP 'vframes'
$clips = Get-ChildItem -LiteralPath $cap -Filter '*.mp4' | Sort-Object LastWriteTime
$n = 0
foreach ($c in $clips) {
  $n++
  $tag = '{0:00}' -f $n
  $vol = & $ff -i $c.FullName -af volumedetect -vn -f null - 2>&1 | Out-String
  $mean = [regex]::Match($vol, 'mean_volume: ([-\d.]+) dB').Groups[1].Value
  $maxv = [regex]::Match($vol, 'max_volume: ([-\d.]+) dB').Groups[1].Value
  Write-Output ('{0} mean={1}dB max={2}dB' -f $tag, $mean, $maxv)
}
# extra frames: 5 per clip for shortlisted clips at 10/30/50/70/90 pct
$short = @(4, 6, 7, 11, 12, 13, 14)
foreach ($n in $short) {
  $c = $clips[$n - 1]
  $info = & $ff -i $c.FullName 2>&1 | Out-String
  $dur = [regex]::Match($info, 'Duration: (\d+):(\d+):([\d.]+)')
  $sec = [int]$dur.Groups[1].Value*3600 + [int]$dur.Groups[2].Value*60 + [double]$dur.Groups[3].Value
  $tag = '{0:00}' -f $n
  $k = 0
  foreach ($p in @(0.1, 0.3, 0.5, 0.7, 0.9)) {
    $k++
    $t = [math]::Round($sec*$p, 1)
    & $ff -y -v error -ss $t -i $c.FullName -frames:v 1 -vf scale=480:-1 (Join-Path $out ($tag + '_' + $k + '.jpg'))
  }
}
Write-Output 'FRAMES DONE'
