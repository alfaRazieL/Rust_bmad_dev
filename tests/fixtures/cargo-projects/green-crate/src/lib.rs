//! Minimal green crate fixture for T-L3-CRATE-001.
//!
//! Used by the L3 integration driver. Should compile under any recent
//! stable Rust if cargo is available in the test environment.

pub fn add(a: i32, b: i32) -> i32 {
    a + b
}

#[cfg(test)]
mod tests {
    use super::add;

    #[test]
    fn adds() {
        assert_eq!(add(2, 3), 5);
    }
}
