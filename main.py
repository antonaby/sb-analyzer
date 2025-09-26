import yt_dlp

def main():
  url = 'https://www.youtube.com/shorts/LX2sA07CX2M'

  ydl_opts = {}
  with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    ydl.download([url])

if __name__ == "__main__":
  main()
 
