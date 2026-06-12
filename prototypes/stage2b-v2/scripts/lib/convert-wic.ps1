param(
  [Parameter(Mandatory = $true)]
  [string]$InputFile,

  [Parameter(Mandatory = $true)]
  [string]$OutputFile
)

Add-Type -AssemblyName PresentationCore

$stream = [System.IO.File]::OpenRead($InputFile)
try {
  $decoder = [System.Windows.Media.Imaging.BitmapDecoder]::Create(
    $stream,
    [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat,
    [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
  )

  $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
  $encoder.Frames.Add($decoder.Frames[0])

  $out = [System.IO.File]::Create($OutputFile)
  try {
    $encoder.Save($out)
  } finally {
    $out.Close()
  }
} finally {
  $stream.Close()
}
