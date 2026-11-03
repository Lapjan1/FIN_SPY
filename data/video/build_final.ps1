$ff = 'C:\Users\dshan\AppData\Local\Programs\Python\Python314-arm64\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-aarch64-v9.0.1.exe'
$cap = Join-Path $env:USERPROFILE 'Videos\Captures'
$clips = Get-ChildItem -LiteralPath $cap -Filter '*.mp4' | Sort-Object LastWriteTime
function Clip($n) { return $clips[$n - 1].FullName }
New-Item -ItemType Directory -Force -Path data/video/cap | Out-Null

# ---- segments: label, kind, src, ss, dur ----
$segs = @(
  @('hook',    'vid', (Clip 11), 0, 10),
  @('folder',  'still', 'data/video/still_folder.png', 0, 6),
  @('dense',   'vid', (Clip 16), 12, 6),
  @('upload',  'vid', (Clip 6), 2, 25),
  @('review',  'vid', (Clip 7), 18, 18),
  @('trial',   'vid', (Clip 10), 2, 7),
  @('drill',   'vid', (Clip 12), 0, 18),
  @('hilite',  'vid', (Clip 13), 18, 8),
  @('spy',     'vid', (Clip 11), 8, 6),
  @('reports', 'vid', (Clip 14), 4, 8),
  @('summary', 'vid', (Clip 16), 4, 6),
  @('verify',  'vid', 'data/video/clip_verify.mp4', 0, 6),
  @('docs',    'still', 'data/video/shot_docs2.png', 0, 8),
  @('close',   'vid', (Clip 2), 2, 14)
)
# ---- overlays: file, text, start, end, style ----
$ovs = @(
  @('t_hook', 'Every rand traced to the exact line - FIN_SPY', 0, 5, 'title'),
  @('c01', 'Bank statements go in - every number comes out with proof.', 5, 10, 'cap'),
  @('c02', 'Small businesses drown in statements.', 10, 16, 'cap'),
  @('c03', 'No AI can show where a number came from.', 16, 22, 'cap'),
  @('c04', 'The file is hashed into an immutable vault.', 22, 30, 'cap'),
  @('c05', 'Same file twice is detected, never duplicated.', 30, 38, 'cap'),
  @('c06', 'Opening plus rows must equal closing - checked both directions.', 38, 47, 'cap'),
  @('c07', 'Private or business, with rationale and confidence.', 47, 55, 'cap'),
  @('c08', 'Accept, and a balanced journal posts.', 55, 63, 'cap'),
  @('c09', 'Trial balance, per bank account. Debits equal credits.', 63, 72, 'cap'),
  @('c10', 'Any number, back to the exact highlighted line.', 72, 85, 'cap'),
  @('c11', 'That is what court-ready means.', 85, 98, 'cap'),
  @('c12', 'The spy finds duplicates and subscriptions.', 98, 106, 'cap'),
  @('c13', 'Exports carry live formulas.', 106, 116, 'cap'),
  @('c14', 'An evidence pack any auditor can verify offline.', 116, 124, 'cap'),
  @('c15', 'Built with Meta Muse Spark.', 124, 132, 'cap'),
  @('c16', '400 tests, live in production today.', 132, 141, 'cap'),
  @('t_end', 'FIN_SPY: every rand, with proof.', 140, 146, 'title')
)
foreach ($o in $ovs) {
  [IO.File]::WriteAllText("data/video/cap/$($o[0]).txt", $o[1], (New-Object Text.UTF8Encoding($false)))
}

# ---- filtergraph ----
$g = @()
for ($i = 0; $i -lt $segs.Count; $i++) {
  $s = $segs[$i]
  if ($s[1] -eq 'vid') {
    $g += ('[{0}:v]scale=1920:1128:force_original_aspect_ratio=decrease,pad=1920:1128:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30[v{0}]' -f $i)
  } elseif ($s[0] -eq 'folder') {
    $frames = $s[4] * 30
    $z = '1+0.08*on/' + ($frames-1)
    $g += ("[{0}:v]scale=869:1128,pad=1920:1128:(ow-iw)/2:(oh-ih)/2:color=0x0f172a,zoompan=z='{1}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1128:fps=30,setsar=1[v{0}]" -f $i, $z)
  } else {
    $frames = $s[4] * 30
    $z = '1+0.06*on/' + ($frames-1)
    $g += ("[{0}:v]scale=1920:1200,crop=1920:1128:0:0,zoompan=z='{1}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1128:fps=30,setsar=1[v{0}]" -f $i, $z)
  }
}
$cat = ''
for ($i = 0; $i -lt $segs.Count; $i++) { $cat += "[v$i]" }
$cat += "concat=n=$($segs.Count):v=1:a=0,format=yuv420p[vcat]"
$g += $cat
$prev = '[vcat]'
$k = 0
foreach ($o in $ovs) {
  if ($o[4] -eq 'title') {
    $dt = "drawtext=fontfile=../../../../../Windows/Fonts/arialbd.ttf:textfile=data/video/cap/$($o[0]).txt:fontsize=56:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=16:x=(w-text_w)/2:y=140:enable=between(t\,$($o[2])\,$($o[3]))"
  } else {
    $dt = "drawtext=fontfile=../../../../../Windows/Fonts/arial.ttf:textfile=data/video/cap/$($o[0]).txt:fontsize=30:fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=12:x=(w-text_w)/2:y=h-96:enable=between(t\,$($o[2])\,$($o[3]))"
  }
  if ($k -eq $ovs.Count - 1) { $g += "$prev$dt[out]" } else { $k2 = $k + 1; $g += "$prev$dt[dt$k2]"; $prev = "[dt$k2]" }
  $k++
}
[IO.File]::WriteAllText('data/video/final_filter.txt', ($g -join ';'), (New-Object Text.UTF8Encoding($false)))

# ---- inputs + run ----
$args = @()
foreach ($s in $segs) {
  if ($s[1] -eq 'vid') { $args += @('-ss', $s[3], '-t', $s[4], '-i', $s[2]) }
  else { $args += @('-framerate', '30', '-loop', '1', '-t', $s[4], '-i', $s[2]) }
}
$graph = [IO.File]::ReadAllText('data/video/final_filter.txt')
$args += @('-filter_complex', $graph, '-map', '[out]',
  '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-r', '30', '-an',
  '-movflags', '+faststart', '-y', 'data/video/FIN_SPY-demo-2m30s.mp4')
& $ff -v warning @args 2> data/video/build.log; Write-Output 'LOGGED, last line:'; Get-Content data/video/build.log | Select-Object -Last 2
Get-Item data/video/FIN_SPY-demo-2m30s.mp4 | Select-Object Name, @{n='MB';e={[math]::Round($_.Length/1MB,1)}}
Write-Output BUILD-DONE
