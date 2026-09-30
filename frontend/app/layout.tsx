import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIVitals | Đo sinh hiệu không tiếp xúc",
  description: "Giao diện đo sinh hiệu bằng camera"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
