package com.example.docintelligence.repository;

import com.example.docintelligence.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;

/** Present for read-only access to the shared users table; reporting joins stay native. */
public interface UserRepository extends JpaRepository<User, String> {
}
