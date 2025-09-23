# R2R Enhanced Template - Supabase Setup Guide

This template is optimized for **Supabase** integration, providing enterprise-grade features like structured data storage, web search caching, and citation logging.

## 🚀 Quick Setup

### 1. Create Supabase Project
1. Go to [supabase.com](https://supabase.com)
2. Create a new project
3. Choose your region (closest to your users)
4. Wait for project initialization

### 2. Run Database Setup
1. Go to **SQL Editor** in your Supabase dashboard
2. Copy and paste the contents of `supabase/setup.sql`
3. Click **Run** to create all tables and functions

### 3. Get Your Credentials
From your Supabase project dashboard:

#### **Settings → Database**
- **Host**: `your-project-ref.supabase.co`
- **Database**: `postgres`
- **User**: `postgres`
- **Password**: Your database password
- **Port**: `5432`

#### **Settings → API**
- **Project URL**: `https://your-project-ref.supabase.co`
- **Anon Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- **Service Role Key**: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (keep secret!)

### 4. Configure Environment
Update your `docker/env/r2r-full.env`:

```bash
# Supabase Database Configuration
POSTGRES_HOST=your-project-ref.supabase.co
POSTGRES_DB=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_supabase_password_here
POSTGRES_PORT=5432

# Supabase API Configuration
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
```

### 5. Start R2R
```bash
./setup-new-project.sh
```

## 🎯 What You Get with Supabase Integration

### **Enhanced Features**
- ✅ **Structured Data Storage** - Spreadsheet cells stored for SQL queries
- ✅ **Document Metadata** - Rich metadata for better citations
- ✅ **Web Search Caching** - Performance optimization for repeated queries
- ✅ **Citation Logging** - Audit trails for all responses
- ✅ **Row Level Security** - Built-in data protection
- ✅ **Real-time Capabilities** - Optional real-time updates
- ✅ **Built-in Auth** - User management out of the box

### **Database Schema**
The setup creates these tables:

#### **`spreadsheet_cells`**
Stores structured data from Excel/CSV files for Tool-Augmented Orchestration:
```sql
document_id | filename | table_name | row_index | column_name | cell_value | data_type
```

#### **`document_metadata`**
Enhanced metadata for better citations:
```sql
document_id | filename | author | title | page_count | word_count | metadata
```

#### **`web_search_cache`**
Caches web search results for performance:
```sql
query_hash | query_text | search_provider | results | expires_at
```

#### **`citation_log`**
Audit trail for all responses:
```sql
query_text | response_text | citations | source_breakdown | confidence_score
```

## 🔧 Advanced Configuration

### **Row Level Security (RLS)**
The setup enables RLS policies for data protection:
- Users can only access their own documents
- Web search cache is shared (public data)
- Citation logs are user-specific

### **Custom Functions**
- `cleanup_expired_web_cache()` - Removes old cache entries
- `get_spreadsheet_data(filename, columns)` - Query spreadsheet data
- `log_citation(...)` - Log responses for audit trails

### **Performance Optimization**
- Indexes on frequently queried columns
- Automatic cache cleanup
- Batch operations for large datasets

## 🌐 Frontend Integration

### **Next.js Example**
```javascript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
)

// Query citation logs
const { data: citations } = await supabase
  .from('citation_log')
  .select('*')
  .order('created_at', { ascending: false })
  .limit(10)

// Query spreadsheet data
const { data: spreadsheetData } = await supabase
  .from('spreadsheet_cells')
  .select('*')
  .eq('filename', 'Q3_Report.xlsx')
```

### **Real-time Updates**
```javascript
// Subscribe to new citations
supabase
  .channel('citations')
  .on('postgres_changes', 
    { event: 'INSERT', schema: 'public', table: 'citation_log' },
    (payload) => {
      console.log('New citation:', payload.new)
    }
  )
  .subscribe()
```

## 📊 Analytics & Monitoring

### **Citation Analytics**
Query citation patterns and performance:
```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as total_queries,
  AVG(confidence_score) as avg_confidence,
  COUNT(*) FILTER (WHERE web_search_used = true) as web_searches
FROM citation_log 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

### **Performance Monitoring**
```sql
-- Web search cache hit rate
SELECT 
  COUNT(*) as total_queries,
  COUNT(*) FILTER (WHERE created_at > updated_at) as cache_hits
FROM web_search_cache;

-- Most queried spreadsheets
SELECT filename, COUNT(*) as query_count
FROM spreadsheet_cells
GROUP BY filename
ORDER BY query_count DESC;
```

## 🔒 Security Best Practices

### **Environment Variables**
- Never commit `.env` files with real credentials
- Use different databases for development/production
- Rotate service role keys regularly

### **RLS Policies**
- Customize RLS policies based on your auth requirements
- Test policies thoroughly before production
- Consider using Supabase Auth for user management

### **API Key Management**
- Use anon key for client-side operations
- Use service role key only for server-side operations
- Implement proper API rate limiting

## 🚀 Production Deployment

### **Scaling Considerations**
- **Database**: Supabase Pro for production workloads
- **Connection Pooling**: Enable for high-traffic applications
- **Backups**: Automatic daily backups included
- **Monitoring**: Use Supabase dashboard for performance metrics

### **Cost Optimization**
- **Free Tier**: Good for development and small projects
- **Pro Tier**: $25/month for production applications
- **Monitor Usage**: Track database size and API requests
- **Cache Strategy**: Leverage web search caching for cost savings

---

**Your R2R template is now Supabase-ready with enterprise-grade features!** 🎊

For questions or issues, check the [Supabase Documentation](https://supabase.com/docs) or [R2R Documentation](https://r2r-docs.sciphi.ai/).
