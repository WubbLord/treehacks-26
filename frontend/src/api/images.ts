import { API_BASE_URL } from "../config";
import type { Pose } from "../types/pose";

type GetImagesResponse = {
  image_base64?: string;
  image?: string;
  imageBase64?: string;
  base64?: string;
  mimeType?: string;
};

function getBase64Field(response: GetImagesResponse): string {
  return (
    response.image_base64 ??
    response.image ??
    response.imageBase64 ??
    response.base64 ??
    ""
  );
}

export async function fetchImageForPose(pose: Pose): Promise<string> {
  const params = new URLSearchParams({
    x: String(pose.x),
    y: String(pose.y),
    z: String(pose.z),
    yaw: String(pose.yaw),
  });

  const url = new URL(API_BASE_URL);
  url.search = params.toString();

  const res = await fetch(url.toString(), {
    method: "GET",
  });

  if (!res.ok) {
    throw new Error(`Request failed (${res.status})`);
  }

  const payload = (await res.json()) as GetImagesResponse;
  const base64 = getBase64Field(payload).trim();

  if (!base64) {
    throw new Error("Image payload is empty");
  }

  const mime = payload.mimeType ?? "image/jpeg";
  return `data:${mime};base64,${base64}`;
}

