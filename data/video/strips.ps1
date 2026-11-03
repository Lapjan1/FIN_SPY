$ff = 'C:\Users\dshan\AppData\Local\Programs\Python\Python314-arm64\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-aarch64-v9.0.1.exe'
$out = Join-Path $env:TEMP 'vframes'
foreach ($n in @((4, 6, 7, 11, 12, 13, 14))) {
  $tag = '{0:00}' -f $n
  $args = @()
  $pads = ''
  for ($k = 0; $k -lt 5; $k++) {
    $args += '-i'; $args += (Join-Path $out ($tag + '_' + ($k + 1) + '.jpg'))
    $pads += '[{0}:v]' -f $k
  }
  $args += @('-filter_complex', ($pads + 'concat=n=5:v=1,tile=5x1'), '-frames:v', '1', '-y', (Join-Path $out ('strip' + $tag + '.jpg')))
  & $ff -v error @args
}
Write-Output 'STRIPS DONE'
