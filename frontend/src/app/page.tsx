"use client";

import { useUser } from "@auth0/nextjs-auth0/client";
import { PublicationGrid } from "@/components/PublicationGrid";
import { UserMenu } from "@/components/UserMenu";
import Image from "next/image";

import "./home.css";

const books = [
  {
    title: "Anna Karenina",
    author: "Leo Tolstoy",
    cover: "",
    url: "/read/anna-karenina",
    rendition: "Reflowable",
  },
  {
    title: "David Copperfield",
    author: "Charles Dickens",
    cover: "",
    url: "/read/david-copperfield",
    rendition: "Reflowable",
  },
];

export default function Home() {
  const { user, isLoading } = useUser();

  if (isLoading) return null;

  return (
    <main id="home">
      <header className="top-header">
        <h1 className="app-title">Apparatus Ebooks</h1>
        {user && <UserMenu user={user} />}
      </header>

      <div className="content">
        <h2 className="page-title">Library</h2>

        <PublicationGrid
          publications={books}
          renderCover={(publication) => (
            <Image
              src={publication.cover}
              alt=""
              loading="lazy"
              width={120}
              height={180}
            />
          )}
        />
      </div>
    </main>
  );
}
