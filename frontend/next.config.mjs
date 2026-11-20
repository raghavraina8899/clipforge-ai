/** @type {import('next').NextConfig} */
// ".nosync" keeps the build output out of iCloud when the project sits in Desktop/Documents.
const nextConfig = { reactStrictMode: false, distDir: ".next.nosync" };
export default nextConfig;
