/** Longest side of the picture that is sent; the server stores a much smaller square anyway. */
const MAX_SIDE = 1024;
const JPEG_QUALITY = 0.86;

/**
 * Makes a chosen picture smaller before it is sent, so a photograph straight from a phone
 * camera fits the upload limit and less data travels. Drawing on a canvas also leaves the
 * camera metadata behind; the server removes it again in any case.
 *
 * When the browser cannot decode or draw the file, the file is returned as it is and the
 * server decides.
 *
 * @param file The file the user chose.
 * @returns A JPEG no larger than 1024 pixels on its longer side, or the original file.
 */
export async function preparePhoto(file: Blob): Promise<Blob> {
  if (typeof createImageBitmap !== "function") return file;
  try {
    const bitmap = await createImageBitmap(file, { imageOrientation: "from-image" });
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(bitmap.width * scale));
    canvas.height = Math.max(1, Math.round(bitmap.height * scale));
    const context = canvas.getContext("2d");
    if (!context) return file;
    // A transparent picture gets a white background, as on the server
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY);
    });
    return blob ?? file;
  } catch {
    return file;
  }
}
