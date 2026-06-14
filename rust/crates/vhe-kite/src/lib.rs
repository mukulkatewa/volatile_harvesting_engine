use reqwest::Client;

pub struct KiteClient {
    http: Client,
}

impl KiteClient {
    pub fn new() -> Self {
        Self {
            http: Client::new(),
        }
    }

    pub fn http(&self) -> &Client {
        &self.http
    }
}

impl Default for KiteClient {
    fn default() -> Self {
        Self::new()
    }
}

