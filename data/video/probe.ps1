$ff = 'C:\Users\dshan\AppData\Local\Programs\Python\Python314-arm64\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-aarch64-v9.0.1.exe'
$cap = Join-Path $env:USERPROFILE 'Videos\Captures'
$out = Join-Path $env:TEMP 'vframes'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$clips = Get-ChildItem -LiteralPath $cap -Filter '*.mp4' | Sort-Object LastWriteTime
$n = 0
foreach ($c in $clips) {
  $n++
  $tag = '{0:00}' -f $n
  $info = & $ff -i $c.FullName 2>&1 | Out-String
  $dur = [regex]::Match($info, 'Duration: (\d+):(\d+):([\d.]+)')
  $sec = 0
  if ($dur.Success) { $sec = [int]$dur.Groups[1].Value*3600 + [int]$dur.Groups[2].Value*60 + [double]$dur.Groups[3].Value }
  $aud = ($info -match 'Audio:')
  $resm = [regex]::Match($info, '(\d{3,5}x\d{3,5})')
  $mid = [math]::Round($sec/2, 1)
  $frame = Join-Path $out ($tag + '.jpg')
  & $ff -y -v error -ss $mid -i $c.FullName -frames:v 1 -vf scale=480:-1 $frame
  Write-Output ('{0} {1}s audio={2} res={3} :: {4}' -f $tag, $sec, $aud, $resm.Groups[1].Value, $c.BaseName.Substring(0, [Math]::Min(60, $c.BaseName.Length)))
}
function Sheet($nums, $name) {
  $args = @()
  $pads = ''
  $k = 0
  foreach ($i in $nums) { $args += '-i'; $args += (Join-Path $out ('{0:00}.jpg' -f $i)); $pads += '[{0}:v]' -f $k; $k++ }
  $args += @('-filter_complex', ($pads + 'concat=n=' + $k + ':v=1,tile=4x2'), '-frames:v', '1', '-y', (Join-Path $out $name))
  & $ff -v error @args
}
Sheet @(1,2,3,4,5,6,7,8) 'sheet1.jpg'
Sheet @(9,10,11,12,13,14,15,16) 'sheet2.jpg'
Write-Output 'SHEETS DONE'
