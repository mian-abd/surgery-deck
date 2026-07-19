// Tiny shared state persisted to localStorage so pages agree on the active
// session and this browser's camera id.

const SESSION_KEY = "orguard.session";
const CAMERA_KEY = "orguard.camera";

export const store = {
  getSession: () => localStorage.getItem(SESSION_KEY) || "",
  setSession: (id: string) => localStorage.setItem(SESSION_KEY, id),
  getCamera: () => localStorage.getItem(CAMERA_KEY) || "",
  setCamera: (id: string) => localStorage.setItem(CAMERA_KEY, id),
};
