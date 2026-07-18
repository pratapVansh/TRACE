declare module "vis-network" {
  export interface Node {
    id?: string;
    label?: string;
    group?: string;
    title?: string;
    color?: string | Record<string, string>;
    borderWidth?: number;
    size?: number;
    shape?: string;
    font?: Record<string, unknown>;
    shadow?: Record<string, unknown>;
    [key: string]: unknown;
  }

  export interface Edge {
    id?: string;
    from?: string;
    to?: string;
    label?: string;
    title?: string;
    width?: number;
    color?: string | Record<string, unknown>;
    font?: Record<string, unknown>;
    smooth?: Record<string, unknown>;
    arrows?: Record<string, unknown>;
    [key: string]: unknown;
  }

  export type IdType = string | number;

  export interface Options {
    nodes?: Record<string, unknown>;
    edges?: Record<string, unknown>;
    physics?: Record<string, unknown>;
    interaction?: Record<string, unknown>;
    layout?: Record<string, unknown>;
    groups?: Record<string, unknown>;
    [key: string]: unknown;
  }

  export class Network {
    constructor(
      container: HTMLElement,
      data: { nodes: DataSet<Node>; edges: DataSet<Edge> },
      options?: Options,
    );
    on(event: string, callback: (...args: unknown[]) => void): void;
    off(event: string, callback: (...args: unknown[]) => void): void;
    destroy(): void;
    focus(nodeId: IdType, options?: Record<string, unknown>): void;
    selectNodes(nodeIds: IdType[]): void;
    getScale(): number;
    getNodes(): { getIds: () => IdType[] };
    getEdges(): { getIds: () => IdType[] };
    getPosition(nodeId: IdType): { x: number; y: number };
    moveTo(options: Record<string, unknown>): void;
    fit(animation?: boolean | Record<string, unknown>): void;
    clustering?: {
      cluster(options?: Record<string, unknown>): void;
    };
    [key: string]: unknown;
  }
}

declare module "vis-data" {
  export class DataSet<T extends Record<string, unknown>> {
    constructor(data?: T[]);
    add(data: T | T[]): IdType[];
    get(id?: IdType | IdType[]): T | T[];
    getIds(): IdType[];
    update(data: T | T[]): IdType[];
    remove(id: IdType | IdType[]): IdType[];
    clear(): void;
    length: number;
    on(event: string, callback: (...args: unknown[]) => void): void;
    off(event: string, callback: (...args: unknown[]) => void): void;
    [key: string]: unknown;
  }

  export type IdType = string | number;
}
