from PIL import Image

size = 48

img = Image.open("icon_not_connected_full.png")
resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
resized_img.save("icon_not_connected.png")

img = Image.open("icon_connected_full.png")
resized_img = img.resize((size, size), Image.Resampling.LANCZOS)
resized_img.save("icon_connected.png")