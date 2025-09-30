export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      categories: {
        Row: {
          id: number;
          user_id: string;
          nom: string;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          nom: string;
          created_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["categories"]["Insert"]>;
        Relationships: [];
      };
      fournisseurs: {
        Row: {
          id: number;
          user_id: string;
          nom: string;
          adresse: string | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          nom: string;
          adresse?: string | null;
          created_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["fournisseurs"]["Insert"]>;
        Relationships: [];
      };
      marques: {
        Row: {
          id: number;
          user_id: string;
          nom: string;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          nom: string;
          created_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["marques"]["Insert"]>;
        Relationships: [];
      };
      produits: {
        Row: {
          id: number;
          user_id: string;
          reference: string | null;
          designation: string | null;
          fournisseur_id: number | null;
          categorie_id: number | null;
          marque_id: number | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          reference?: string | null;
          designation?: string | null;
          fournisseur_id?: number | null;
          categorie_id?: number | null;
          marque_id?: number | null;
          created_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["produits"]["Insert"]>;
        Relationships: [];
      };
      factures: {
        Row: {
          id: number;
          user_id: string;
          fournisseur_id: number;
          numero: string;
          date: string;
          nom_fichier: string;
          total_ht: number | null;
          tva_amount: number | null;
          total_ttc: number | null;
          nombre_colis: number | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          fournisseur_id: number;
          numero: string;
          date: string;
          nom_fichier: string;
          total_ht?: number | null;
          tva_amount?: number | null;
          total_ttc?: number | null;
          nombre_colis?: number | null;
          created_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["factures"]["Insert"]>;
        Relationships: [];
      };
      lignes_facture: {
        Row: {
          id: number;
          user_id: string;
          facture_id: number;
          produit_id: number;
          prix_unitaire: number | null;
          collisage: number | null;
          quantite: number | null;
          montant: number | null;
          created_at: string | null;
        };
        Insert: {
          id?: number;
          user_id: string;
          facture_id: number;
          produit_id: number;
          prix_unitaire?: number | null;
          collisage?: number | null;
          quantite?: number | null;
          montant?: number | null;
          created_at?: string | null;
        };
        Update: Partial<Database["public"]["Tables"]["lignes_facture"]["Insert"]>;
        Relationships: [];
      };
      top_products_raw_view: {
        Row: Record<string, Json>;
        Insert: Record<string, Json>;
        Update: Record<string, Json>;
        Relationships: [];
      };
      ttc_by_fournisseur_view: {
        Row: Record<string, Json>;
        Insert: Record<string, Json>;
        Update: Record<string, Json>;
        Relationships: [];
      };
      ttc_by_category_view: {
        Row: Record<string, Json>;
        Insert: Record<string, Json>;
        Update: Record<string, Json>;
        Relationships: [];
      };
    };
  };
}
