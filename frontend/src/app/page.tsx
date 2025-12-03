"use client";

import { useEffect, useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { PublicationGrid } from "@/components/PublicationGrid";
import Image from "next/image";

import { isManifestRouteEnabled } from "./ManifestRouteEnabled";

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

const onlineBooks = [
  {
    title: "Accessible EPUB3",
    author: "Matt Garrish",
    cover: "/images/accessibleEpub3.jpg",
    url: "/read/manifest/https%3A%2F%2Fpublication-server.readium.org%2FaHR0cHM6Ly9naXRodWIuY29tL0lEUEYvZXB1YjMtc2FtcGxlcy9yZWxlYXNlcy9kb3dubG9hZC8yMDIzMDcwNC9hY2Nlc3NpYmxlX2VwdWJfMy5lcHVi%2Fmanifest.json",
    rendition: "Reflowable",
  },
  {
    title: "Children Literature",
    author: "Charles Madison Curry, Erle Elsworth Clippinger",
    cover: "/images/ChildrensLiterature.png",
    url: "/read/manifest/https%3A%2F%2Fpublication-server.readium.org%2FaHR0cHM6Ly9naXRodWIuY29tL0lEUEYvZXB1YjMtc2FtcGxlcy9yZWxlYXNlcy9kb3dubG9hZC8yMDIzMDcwNC9jaGlsZHJlbnMtbGl0ZXJhdHVyZS5lcHVi%2Fmanifest.json",
    rendition: "Reflowable",
  },
];

export default function Home() {
  const [isManifestEnabled, setIsManifestEnabled] = useState<boolean>(true);
  const [protectedMessage, setProtectedMessage] = useState<string | null>(null);
  const [protectedError, setProtectedError] = useState<string | null>(null);
  const [isCallingProtected, setIsCallingProtected] = useState<boolean>(false);

  const { user, isLoading } = useUser();

  const onCallProtectedClick = async () => {
    setIsCallingProtected(true);
    setProtectedError(null);

    try {
      const response = await fetch("/api/protected");

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data: { message?: string } = await response.json();
      console.log(data);
      setProtectedMessage(
        data.message ?? "Received response from protected API.",
      );
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Unknown error occurred while calling the protected API.";
      setProtectedError(message);
      setProtectedMessage(null);
    } finally {
      setIsCallingProtected(false);
    }
  };

  useEffect(() => {
    const checkManifestRoute = async () => {
      try {
        const enabled = await isManifestRouteEnabled();
        setIsManifestEnabled(enabled);
      } catch (error) {
        console.error("Error checking manifest route:", error);
        setIsManifestEnabled(false);
      }
    };

    checkManifestRoute();
  }, []);

  if (isLoading) return null;

  return (
    <main id="home">
      <header className="header">
        <h1>Welcome to Thorium Web</h1>

        <p className="subtitle">
          An open-source ebook/audiobook/comics Web Reader
        </p>
        {user && <p>Welcome {user.name}</p>}
        <p>
          <a href="/auth/logout">Logout</a>
        </p>
        <button
          type="button"
          onClick={onCallProtectedClick}
          disabled={isCallingProtected}
        >
          {isCallingProtected
            ? "Calling Protected API..."
            : "Call Protected API"}
        </button>
        <div aria-live="polite">
          {protectedMessage && <p>{protectedMessage}</p>}
          {protectedError && <p>{protectedError}</p>}
        </div>
      </header>

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

      {isManifestEnabled && (
        <>
          <div className="dev-books">
            <p>
              In dev you can also use the <code>/manifest/</code> route to load
              any publication. For instance:
            </p>

            <PublicationGrid
              publications={onlineBooks}
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
        </>
      )}
    </main>
  );
}
