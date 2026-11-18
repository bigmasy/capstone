import { baseApi } from "./baseApi";

/** What the server accepts; the picture is stored again as a small square JPEG. */
export const PHOTO_ACCEPT = "image/jpeg,image/png,image/webp";
/** Largest upload the server reads, in bytes. */
export const PHOTO_MAX_BYTES = 2 * 1024 * 1024;

/**
 * True when the server refused an upload because the file is not a picture or is too large
 * (HTTP 422 with a reason code).
 */
export function photoRejection(error: unknown): "photo_invalid" | "photo_too_large" | null {
  const failure = error as { status?: unknown; data?: { code?: unknown } } | undefined;
  if (failure?.status !== 422) return null;
  return failure.data?.code === "photo_too_large" ? "photo_too_large" : "photo_invalid";
}

/** Reads a small picture into a `data:` URL. */
function toDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("the picture could not be read"));
    };
    reader.onerror = () => reject(new Error("the picture could not be read"));
    reader.readAsDataURL(blob);
  });
}

export const photoApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    /**
     * The photograph of a profile as a `data:` URL. The route needs the bearer token, which an
     * `img` element cannot send, so the picture is fetched here. A `data:` URL is used because
     * the content security policy of the site allows it for images and does not allow `blob:`.
     */
    getProfilePhoto: build.query<string, string>({
      query: (profileId) => ({
        url: `/profiles/${profileId}/photo`,
        responseHandler: async (response) =>
          response.ok ? toDataUrl(await response.blob()) : response.text(),
      }),
      providesTags: (_url, _error, profileId) => [{ type: "Photo", id: profileId }],
    }),
    /** Uploads the caller's photograph; the body is the picture itself. */
    uploadMyPhoto: build.mutation<void, { profileId: string; file: Blob }>({
      query: ({ file }) => ({
        url: "/profiles/me/photo",
        method: "PUT",
        headers: { "Content-Type": file.type || "application/octet-stream" },
        body: file,
      }),
      invalidatesTags: (_result, error, { profileId }) =>
        error ? [] : ["Profile", { type: "Photo", id: profileId }],
    }),
    /** Deletes the caller's photograph. */
    deleteMyPhoto: build.mutation<void, { profileId: string }>({
      query: () => ({ url: "/profiles/me/photo", method: "DELETE" }),
      invalidatesTags: (_result, error, { profileId }) =>
        error ? [] : ["Profile", { type: "Photo", id: profileId }],
    }),
  }),
});

export const { useGetProfilePhotoQuery, useUploadMyPhotoMutation, useDeleteMyPhotoMutation } =
  photoApi;
