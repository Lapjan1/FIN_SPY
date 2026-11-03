$ff = 'C:\Users\dshan\AppData\Local\Programs\Python\Python314-arm64\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-aarch64-v9.0.1.exe'
$cap = Join-Path $env:USERPROFILE 'Videos\Captures'
$clips = Get-ChildItem -LiteralPath $cap -Filter '*.mp4' | Sort-Object LastWriteTime
# clipN, startSec, durSec
$segs = @(
  @(11, 0, 10), (1, 2, 12), (6, 2, 25), (7, 18, 18), (10, 2, 7),
  (12, 3, 15), (11, 8, 6), (14, 4, 8), (16, 8, 12), (2, 4, 10)
)
$args = @()
$pads = ''
$k = 0
foreach ($s in $segs) {
  $args += @('-ss', $s[1], '-t', $s[2], '-i', $clips[$s[0] - 1].FullName)
  $pads += '[{0}:v][{0}:a]' -f $k
  $k++
}
$args += @('-filter_complex', ($pads + 'concat=n=' + $k + ':v=1:a=1'),
  '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac',
  '-movflags', '+faststart', '-y', 'data/video/preview-v1.mp4')
& $ff -v error @args
Write-Output 'PREVIEW DONE'
Get-Item data/video/preview-v1.mp4 | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
