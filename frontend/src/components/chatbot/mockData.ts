import { makeId } from "./utils";

interface MessageType {
	id: string;
	role: "user" | "assistant";
	content: string;
	createdAt: string;
}

interface Conversation {
	id: string;
	title: string;
	updatedAt: string;
	messageCount: number;
	preview: string;
	pinned: boolean;
	folder: string | null;
	messages: MessageType[];
}

interface Template {
	id: string;
	name: string;
	content: string;
	snippet: string;
	createdAt: string;
	updatedAt: string;
}

interface Folder {
	id: string;
	name: string;
}

export const INITIAL_CONVERSATIONS: Conversation[] = [];

export const INITIAL_TEMPLATES: Template[] = [];

export const INITIAL_FOLDERS: Folder[] = [];
