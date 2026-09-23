import { logger } from "@/lib/logger";
/**
 * Simple event emitter for cross-component communication
 * Used to refresh invoice lists when invoices are updated
 */

type EventCallback = () => void;

class EventEmitter {
	private events: Map<string, Set<EventCallback>> = new Map();

	on(event: string, callback: EventCallback) {
		if (!this.events.has(event)) {
			this.events.set(event, new Set());
		}
		this.events.get(event)!.add(callback);

		// Return unsubscribe function
		return () => {
			this.events.get(event)?.delete(callback);
		};
	}

	emit(event: string) {
		const callbacks = this.events.get(event);
		logger.debug(
			`📢 Event emitted: ${event}, listeners: ${callbacks?.size || 0}`
		);
		if (callbacks) {
			callbacks.forEach((callback) => callback());
		}
	}

	off(event: string, callback: EventCallback) {
		this.events.get(event)?.delete(callback);
	}
}

// Export singleton instance
export const eventBus = new EventEmitter();

// Event names
export const EVENTS = {
	INVOICE_UPDATED: "invoice:updated",
	INVOICE_CREATED: "invoice:created",
	INVOICE_DELETED: "invoice:deleted",
} as const;
